//! One reusable Windows thread for a caller's synchronous host compiles.
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};
use std::sync::{Arc, mpsc};
use std::thread::{self, JoinHandle};
use windows::Win32::Foundation::{HANDLE, WAIT_OBJECT_0};
use windows::Win32::System::Threading::{
    CreateEventW, GetCurrentThread, INFINITE, SetEvent, SetThreadPriority,
    THREAD_PRIORITY_BELOW_NORMAL, WaitForMultipleObjects,
};

pub(super) struct Worker<J, R> {
    jobs: mpsc::Sender<J>,
    results: mpsc::Receiver<R>,
    completed: Arc<OwnedHandle>,
    thread: JoinHandle<()>,
}

impl<J: Send + 'static, R: Send + 'static> Worker<J, R> {
    pub(super) fn spawn(compile: impl Fn(J) -> R + Send + 'static) -> std::io::Result<Self> {
        // SAFETY: CreateEventW returns a new owned handle. Auto-reset consumes one
        // completion per call. There is only one caller and one outstanding job.
        let completed = unsafe {
            Arc::new(OwnedHandle::from_raw_handle(
                CreateEventW(None, false, false, None)?.0,
            ))
        };
        let signal = completed.clone();
        let (jobs, requests) = mpsc::channel();
        let (replies, results) = mpsc::channel();
        let thread = thread::Builder::new()
            .name("victory-pipeline-compile".into())
            .stack_size(8 << 20)
            .spawn(move || {
                // SAFETY: changes the priority of this thread only.
                unsafe {
                    let _ = SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);
                }
                for job in requests {
                    if replies.send(compile(job)).is_err() {
                        break;
                    }
                    // SAFETY: this thread owns a reference to the event throughout the loop.
                    if unsafe { SetEvent(HANDLE(signal.as_raw_handle())) }.is_err() {
                        break;
                    }
                }
            })?;
        Ok(Self {
            jobs,
            results,
            completed,
            thread,
        })
    }

    pub(super) fn run(&mut self, job: J) -> Option<R> {
        self.jobs.send(job).ok()?;
        let handles = [
            HANDLE(self.completed.as_raw_handle()),
            HANDLE(self.thread.as_raw_handle()),
        ];
        // SAFETY: both handles are live until this call returns. A driver may
        // end its thread without dropping the Rust sender, so the channel alone
        // cannot be used to decide whether a reply is still possible.
        let wait = unsafe { WaitForMultipleObjects(&handles, false, INFINITE) };
        if wait != WAIT_OBJECT_0 {
            return None;
        }
        self.results.try_recv().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn successive_compiles_run_on_the_same_thread_and_deliver_distinct_replies() {
        let mut worker = Worker::spawn(|value: i32| (thread::current().id(), value + 1)).unwrap();
        let (id, answer) = worker.run(10).unwrap();
        assert_ne!(id, thread::current().id());
        assert_eq!(answer, 11);
        for value in 0..256 {
            assert_eq!(worker.run(value), Some((id, value + 1)));
        }
    }

    #[test]
    fn worker_exit_releases_the_waiter_and_a_new_worker_can_run() {
        let mut worker = Worker::spawn(|stop: bool| {
            assert!(!stop, "test worker exit");
            17
        })
        .unwrap();
        assert_eq!(worker.run(false), Some(17));
        assert_eq!(worker.run(true), None);
        drop(worker);
        let mut replacement = Worker::spawn(|value| value).unwrap();
        assert_eq!(replacement.run(42), Some(42));
    }
}
