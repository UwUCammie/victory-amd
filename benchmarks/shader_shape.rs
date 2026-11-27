//! Run the same translator with two option sets and compare private size and identity data.

use std::{
    env, fs,
    io::{self, BufRead, Write},
    path::PathBuf,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    victory_shader::emit::set_host_rdna(true);
    victory_shader::emit::set_host_max_wave(64);
    let root = PathBuf::from(env::args_os().nth(1).expect("corpus directory"));
    #[cfg(windows)]
    let mut validator = env::var_os("VICTORY_DXIL")
        .map(|path| victory_shader::emit::validator::Validator::load(Some(PathBuf::from(path).as_path())))
        .transpose()?;
    let mut out = io::BufWriter::new(io::stdout().lock());
    for path in io::stdin().lock().lines() {
        let bytes = fs::read(root.join(path?))?;
        match victory_shader::emit::translate(&bytes) {
            Ok(mut shader) => {
                let size = shader.dxil.len();
                let code = blake3::hash(&shader.dxil);
                #[cfg(windows)]
                if let Some(validator) = validator.as_mut() {
                    validator.validate(&mut shader.dxil)?;
                }
                shader.dxil.clear();
                let metadata = blake3::hash(format!("{shader:?}").as_bytes());
                writeln!(out, "ok\t{:?}\t{size}\t{code}\t{metadata}", shader.stage)?;
            }
            Err(error) => {
                let reason = blake3::hash(error.to_string().as_bytes());
                writeln!(out, "error\t-\t0\t-\t{reason}")?;
            }
        }
    }
    Ok(())
}
