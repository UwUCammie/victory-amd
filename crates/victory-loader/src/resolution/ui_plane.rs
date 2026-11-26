//! Let the title lay out the interface at its design resolution and use its
//! second present plane for the result. The compositor downsamples that plane
//! onto the 720p scene. This also covers fixed-pixel panels and opening credits.

use super::{OUTPUT, Site};
use std::ffi::OsStr;

pub(super) fn requested(output: (u32, u32), setting: Option<&OsStr>, planes: Option<&OsStr>) -> bool {
    output == (1280, 720) && setting == Some(OsStr::new("1")) && planes != Some(OsStr::new("0"))
}

// The display initializer chooses a 64 MiB pool for the single plane and
// an 82 MiB pool for the split display. Use the latter to fit both pairs
// of buffers, including the interface at 3840×2160.
const SINGLE_POOL: [u8; 4] = (64u32 << 20).to_le_bytes();
pub(super) const SPLIT_POOL: [u8; 4] = (82u32 << 20).to_le_bytes();
pub(super) const POOL: Site = Site {
    at: 0x247ad4b,
    what: "separate interface plane display pool",
    bytes: &SINGLE_POOL,
};

pub(super) fn output_code() -> Vec<u8> {
    // At this point RSI holds the video settings. Width and height are
    // consecutive u32 fields in both resolutionFullscreen and uiResolution.
    let mut prefix = vec![0x48, 0x8d, 0x8e]; // lea rcx, [rsi + uiOverlay]
    prefix.extend(0x1e8u32.to_le_bytes());
    prefix.extend([0x48, 0xb8]); // mov rax, packed output size
    prefix.extend(1280u32.to_le_bytes());
    prefix.extend(720u32.to_le_bytes());
    prefix.extend([0x48, 0x89, 0x41, 0x1c]); // resolutionFullscreen = rax
    prefix.extend([0x48, 0x8d, 0x14, 0x40]); // lea rdx, [rax + 2*rax]: 3840×2160
    prefix.extend([0x48, 0x89, 0x51, 0x04]); // uiResolution = rdx
    prefix.extend([0xc6, 0x01, 0x01]);       // uiOverlay = true
    prefix.extend([0x8b, 0x79, 0x20]);       // edi = output height; eax still holds width
    // The rest of the original block sets the screen size and only notifies
    // the renderer if the height changed. Its branches stay at the same addresses.
    let mut code = OUTPUT.bytes.to_vec();
    code[..prefix.len()].copy_from_slice(&prefix);
    code
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requires_a_720p_output_and_an_enabled_compositor() {
        let on = Some(OsStr::new("1"));
        let off = Some(OsStr::new("0"));
        assert!(requested((1280, 720), on, None));
        assert!(requested((1280, 720), on, on));
        assert!(!requested((1280, 720), on, off));
        assert!(!requested((1280, 720), None, on));
        assert!(!requested((1920, 1080), on, on));
    }

    #[test]
    fn keeps_the_title_size_setter_and_separates_scene_and_interface() {
        let code = output_code();
        let size = u64::from_le_bytes(code[9..17].try_into().unwrap());
        let unpack = |s: u64| (s as u32, (s >> 32) as u32);
        assert_eq!(unpack(size), (1280, 720));
        assert_eq!(unpack(3 * size), (3840, 2160));
        assert_eq!(code.len(), OUTPUT.bytes.len());
        assert_eq!(code[35..], OUTPUT.bytes[35..]);
        assert_eq!(u32::from_le_bytes(SPLIT_POOL) - u32::from_le_bytes(SINGLE_POOL), 18 << 20);
    }
}
