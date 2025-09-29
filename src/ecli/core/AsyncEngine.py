# ecli/core/AsyncEngine.py
"""AsyncEngine Module
==================
This module provides the `AsyncEngine` class, which enables the execution of asynchronous tasks in a dedicated background thread using Python's `asyncio` event loop. It is designed to offload long-running or I/O-bound operations—such as communication with Language Server Protocol (LSP) clients or AI chat services—from the main user interface (UI) thread, ensuring that the UI remains responsive.
Key Features:
-------------
- Runs an asyncio event loop in a separate thread to handle asynchronous tasks without blocking the main UI.
- Supports safe communication between threads using thread-safe queues.
- Dynamically dispatches tasks (e.g., AI chat requests) to appropriate async handlers.
- Provides robust error handling and graceful shutdown of background tasks and the event loop.
- Easily extensible to support additional asynchronous task types.
Intended Usage:
---------------
Integrate `AsyncEngine` into applications that require concurrent execution of asynchronous operations alongside a synchronous UI, such as terminal-based editors or tools with real-time AI or LSP integrations.
Classes:
--------
- AsyncEngine: Manages the lifecycle of the asyncio event loop, task submission, execution, and result delivery between threads.
Dependencies:
-------------
- asyncio
- threading
- queue
- logging
- typing
- ecli.integrations.AI (for AI client integration)
"""

import asyncio
import logging
import queue
import threading
from typing import Any, Optional, cast

from ecli.integrations.AI import BaseAiClient, get_ai_client


# Let's define an alias for the queue elements to avoid repetition.
# The queue can receive tasks (dictionaries) or None to stop.
QueueItem = Optional[dict[str, Any]]


# ==================== AsyncEngine Class ====================
class AsyncEngine:
    """Class AsyncEngine
    ===================
    The `AsyncEngine` class is responsible for managing an asyncio event loop in a background thread.
    AsyncEngine runs an asyncio event loop in a dedicated background thread to handle
    long-running and I/O-bound asynchronous tasks, such as Language Server Protocol (LSP)
    clients and AI chat clients, without blocking the main UI thread.
    This engine enables seamless integration of asynchronous operations within a synchronous
    application, such as a curses-based UI, by providing thread-safe task submission and
    result communication mechanisms.

    Attributes:
        loop (Optional[asyncio.AbstractEventLoop]): The asyncio event loop running in the background thread.
        thread (Optional[threading.Thread]): The background thread running the event loop.
        from_ui_queue (queue.Queue): Thread-safe queue for receiving tasks from the UI thread.
        to_ui_queue (queue.Queue): Thread-safe queue for sending results back to the UI thread.
        _tasks (set): Set of currently running asyncio tasks.
        config (dict): Configuration dictionary for engine and client setup.

    Methods:
        start():
            Starts the asyncio event loop in a background thread.
        submit_task(task_data: Dict[str, Any]):
            Thread-safe method for the UI thread to submit a new asynchronous task.
        stop():
            Gracefully stops the event loop and background thread, ensuring all tasks are cancelled.
        main_loop():
            The main asynchronous loop that listens for tasks from the UI thread and dispatches them.
        dispatch_task(task_data: Dict[str, Any]):
            Dispatches a received task to the appropriate asynchronous handler based on its type.
        _shutdown_tasks():
            Cancels all outstanding asynchronous tasks before shutting down the event loop.
    """

    def __init__(
        self, to_ui_queue: queue.Queue[dict[str, Any]], config: dict[str, Any]
    ) -> None:
        """Initializes the AsyncEngine instance.

        Args:
            to_ui_queue (queue.Queue): A thread-safe queue used to send results back to the main UI thread.
            config (dict): Configuration dictionary for the AsyncEngine.

        Attributes:
            loop (Optional[asyncio.AbstractEventLoop]): The asyncio event loop used for asynchronous operations.
            thread (Optional[threading.Thread]): The thread running the event loop.
            from_ui_queue (queue.Queue): A thread-safe queue for receiving messages from the UI.
            to_ui_queue (queue.Queue): A thread-safe queue for sending messages to the UI.
            _tasks (set): A set to keep track of running asynchronous tasks.
            config (dict): Configuration settings for the AsyncEngine.
        """
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        # from_ui_queue accepts tasks and stop signal (None)
        self.from_ui_queue: queue.Queue[QueueItem] = queue.Queue()
        # to_ui_queue sends only dictionaries with results
        self.to_ui_queue: queue.Queue[dict[str, Any]] = to_ui_queue
        self._tasks: set[asyncio.Task[Any]] = set()
        self.config: dict[str, Any] = config
        self._stop_event = asyncio.Event()

    def _start_loop_in_thread(self) -> None:
        """Internal method to set up and run the event loop."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.main_loop())
        finally:
            # Check that loop was created before accessing it
            if self.loop:
                if self.loop.is_running():
                    self.loop.stop()
                self.loop.close()
            logging.info("AsyncEngine event loop has shut down.")

    def start(self) -> None:
        """Starts the asyncio event loop in a background thread."""
        if self.thread is not None:
            logging.warning("AsyncEngine already started.")
            return
        logging.info("Starting AsyncEngine background thread...")
        self.thread = threading.Thread(
            target=self._start_loop_in_thread, daemon=True, name="AsyncEngineThread"
        )
        self.thread.start()

    async def main_loop(self) -> None:
        """The main async loop that listens for tasks from the UI thread.
        It runs until a stop signal (None) is received.
        """
        if not self.loop:
            logging.error("Event loop not initialized before starting main_loop.")
            return

        logging.info("AsyncEngine main_loop is running and waiting for tasks.")

        while True:
            try:
                # Safely wait for a task from the queue
                task_data = await self.loop.run_in_executor(
                    None, self.from_ui_queue.get
                )

                # Signal to stop the loop
                if task_data is None:
                    logging.info(
                        "AsyncEngine received stop signal. Breaking main_loop."
                    )
                    break

                # Run the task processing as a background asyncio.Task
                task = self.loop.create_task(self.dispatch_task(task_data))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            except Exception as e:
                # If the loop is still running, this is a real error
                if self.loop and self.loop.is_running():
                    logging.error(
                        f"Critical error in AsyncEngine main_loop: {e}", exc_info=True
                    )
                    await asyncio.sleep(1)
                else:  # Error during shutdown, likely normal
                    logging.info(
                        "Exception in main_loop during shutdown, likely normal"
                    )
                    break

        # Before exiting `main_loop`, cancel all remaining tasks.
        await self._shutdown_tasks()

    async def dispatch_task(self, task_data: dict[str, Any]) -> None:
        """Dispatches a task to the correct async handler based on its type."""
        task_type = task_data.get("type")
        logging.debug(f"AsyncEngine dispatching task of type: {task_type}")

        ai_client: Optional[BaseAiClient] = None

        try:
            if task_type == "ai_chat":
                provider = task_data.get("provider")
                prompt = task_data.get("prompt")
                config = task_data.get("config")

                if not (
                    isinstance(provider, str)
                    and isinstance(prompt, str)
                    and isinstance(config, dict)
                ):
                    raise ValueError(
                        "Missing or invalid 'provider', 'prompt', or 'config' for ai_chat task."
                    )
                # Create AI client based on provider and config
                # `config` originates as `dict[str, Any]` but some type checkers
                # may treat it as a broader `dict[Unknown, Unknown]`. Use
                # `cast` to narrow the type for `get_ai_client`.
                ai_client = get_ai_client(provider, cast(dict[str, Any], config))
                reply_text = await ai_client.ask_async(
                    prompt, system_msg="You are a helpful assistant."
                )  # Added default system_msg

                # Send the result back to the UI
                self.to_ui_queue.put(
                    {"type": "ai_reply", "provider": provider, "text": reply_text}
                )

            else:
                logging.warning(f"AsyncEngine received unknown task type: {task_type}")

        except Exception as e:
            error_message = f"Error executing async task '{task_type}': {e}"
            logging.error(error_message, exc_info=True)
            # Send error message back to UI
            self.to_ui_queue.put(
                {"type": "task_error", "task_type": task_type, "error": str(e)}
            )

        finally:
            # Important: always close the client session
            if ai_client:
                await ai_client.close()

    def submit_task(self, task_data: dict[str, Any]) -> None:
        """Thread-safe method for the UI thread to submit a task."""
        self.from_ui_queue.put(task_data)

    async def _shutdown_tasks(self) -> None:
        """Internal coroutine to cancel all running async tasks."""
        if not self._tasks:
            return
        logging.info(f"Cancelling {len(self._tasks)} outstanding async tasks...")
        tasks_to_cancel = list(self._tasks)
        for task in tasks_to_cancel:
            task.cancel()

        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        logging.info("All async tasks cancelled.")

    def stop(self) -> None:
        """Gracefully and thread-safely stops the asyncio event loop and its tasks."""
        if not self.thread or not self.loop or not self.thread.is_alive():
            logging.debug(
                "AsyncEngine.stop() called, but no active loop or thread to stop."
            )
            return

        logging.info("Stopping AsyncEngine...")

        try:
            # Send None signal to the queue to exit the main_loop
            self.from_ui_queue.put(None)
            logging.info("Sent stop signal to AsyncEngine main_loop.")

            # Wait for the thread to finish
            self.thread.join(timeout=2.0)

            if self.thread.is_alive():
                logging.error(
                    "AsyncEngine thread did not stop gracefully within the timeout."
                )
                # Forcefully stop the event loop from another thread
                self.loop.call_soon_threadsafe(self.loop.stop)
            else:
                logging.info(
                    "AsyncEngine thread has been successfully stopped and joined."
                )

        except Exception as e:
            logging.error(
                f"An exception occurred while stopping AsyncEngine thread: {e}",
                exc_info=True,
            )
