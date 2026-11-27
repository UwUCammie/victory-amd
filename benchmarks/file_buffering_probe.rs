//! Observe the Win32 file modes and keep both synthetic handles open for the host probe.
use std::ffi::{OsStr, c_void};
use std::io::{self, Write};
use std::os::windows::ffi::OsStrExt;
use std::ptr::{null, null_mut};

type Handle = *mut c_void;
const NO_BUFFERING: u32 = 0x2000_0000;
const NT_NO_INTERMEDIATE_BUFFERING: u32 = 8;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateFileW(
        path: *const u16,
        access: u32,
        sharing: u32,
        attrs: *const c_void,
        disposition: u32,
        flags: u32,
        template: Handle,
    ) -> Handle;
    fn ReadFile(
        file: Handle,
        buffer: *mut u8,
        bytes: u32,
        got: *mut u32,
        overlapped: *mut c_void,
    ) -> i32;
    fn CloseHandle(file: Handle) -> i32;
}

#[link(name = "ntdll")]
unsafe extern "system" {
    fn NtQueryInformationFile(
        file: Handle,
        iosb: *mut IoStatus,
        buffer: *mut u32,
        len: u32,
        class: u32,
    ) -> i32;
}

#[repr(C)]
struct IoStatus {
    status_or_pointer: usize,
    information: usize,
}

#[repr(align(4096))]
struct Block([u8; 4096]);

struct File(Handle);

impl Drop for File {
    fn drop(&mut self) {
        // SAFETY: the handle was opened successfully and is owned by this File.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

fn open_and_read(path: &OsStr, flags: u32) -> (File, u32) {
    let wide: Vec<_> = path.encode_wide().chain([0]).collect();
    // SAFETY: a NUL-terminated path, with default security and no template.
    let handle =
        unsafe { CreateFileW(wide.as_ptr(), 0x8000_0000, 1, null(), 3, flags, null_mut()) };
    assert_ne!(
        handle as isize,
        -1,
        "CreateFileW: {}",
        io::Error::last_os_error()
    );
    let file = File(handle);
    let mut mode = 0;
    let mut status = IoStatus {
        status_or_pointer: 0,
        information: 0,
    };
    // SAFETY: a valid handle and the writable FILE_MODE_INFORMATION and status buffers.
    let ntstatus = unsafe { NtQueryInformationFile(file.0, &mut status, &mut mode, 4, 16) };
    assert_eq!(ntstatus, 0, "FileModeInformation");

    let mut block = Block([0; 4096]);
    let mut got = 0;
    // SAFETY: the block is writable and aligned, and the handle uses synchronous IO.
    let read = unsafe { ReadFile(file.0, block.0.as_mut_ptr(), 4096, &mut got, null_mut()) };
    assert_ne!(read, 0, "ReadFile: {}", io::Error::last_os_error());
    assert_eq!(got, 4096);
    assert!(
        block
            .0
            .iter()
            .enumerate()
            .all(|(i, &b)| b == (7 * i + i / 257) as u8)
    );
    (file, mode)
}

fn main() {
    let paths: Vec<_> = std::env::args_os().skip(1).collect();
    let (_buffered, buffered_mode) = open_and_read(&paths[0], 0);
    let (_unbuffered, unbuffered_mode) = open_and_read(&paths[1], NO_BUFFERING);
    assert_eq!(buffered_mode & NT_NO_INTERMEDIATE_BUFFERING, 0);
    assert_eq!(
        unbuffered_mode & NT_NO_INTERMEDIATE_BUFFERING,
        NT_NO_INTERMEDIATE_BUFFERING
    );
    println!("ready {buffered_mode:#x} {unbuffered_mode:#x}");
    io::stdout().flush().unwrap();
    io::stdin().read_line(&mut String::new()).unwrap();
}
