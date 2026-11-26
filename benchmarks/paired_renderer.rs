//! Build with rustc --edition 2024 -O benchmarks/paired_renderer.rs.
use std::fs::File;
use std::io::{self, BufRead, BufReader};

const ORDER: [bool; 8] = [false, true, true, false, true, false, false, true];

#[derive(Default, Debug)]
struct Sample {
    enabled: bool,
    frames: u64,
    micros: u64,
    draws: u64,
    units: u64,
    kind: &'static str,
}

impl Sample {
    fn fps(&self) -> f64 {
        self.frames as f64 * 1e6 / self.micros as f64
    }
}

fn plain(line: &str) -> String {
    let mut escape = false;
    line.chars()
        .filter(|&c| {
            if escape {
                if c == 'm' {
                    escape = false;
                }
                false
            } else if c == '\x1b' {
                escape = true;
                false
            } else {
                true
            }
        })
        .collect()
}

fn field<'a>(record: &'a str, name: &str) -> Result<&'a str, String> {
    record
        .split_whitespace()
        .filter_map(|w| w.split_once('='))
        .find_map(|(key, value)| (key == name).then_some(value))
        .ok_or_else(|| format!("Missing {name}"))
}

fn collect(
    reader: impl BufRead,
    blocks: usize,
    min_draws: u64,
    live: bool,
) -> Result<Vec<Sample>, String> {
    let mut rows = Vec::new();
    let mut seconds = None;
    for raw in reader.lines() {
        let line = plain(&raw.map_err(|e| e.to_string())?);
        let lower = line.to_ascii_lowercase();
        if [
            "device removed:",
            "gpuvm fault",
            "panicked at",
            "unhandled exception",
        ]
        .iter()
        .any(|s| lower.contains(s))
        {
            return Err("Runtime or device failure in log".into());
        }
        let (rec, kind, counter) =
            if let Some((_, rec)) = line.split_once("victory_bench: renderer trial") {
                let kind = match field(rec, "kind")?.trim_matches('"') {
                    "descriptors" => "slots skipped",
                    "card_sync" => "buffers batched",
                    "shadow_cache" => "cached lookups (groups of 256)",
                    "changed_runs" => "MiB compared with AVX2",
                    other => return Err(format!("Unknown renderer trial {other}")),
                };
                (rec, kind, "work_units")
            } else if let Some((_, rec)) = line.split_once("victory_bench: descriptor trial") {
                (rec, "slots skipped", "cold_slots")
            } else {
                continue;
            };
        if rows.first().is_some_and(|s: &Sample| s.kind != kind) {
            return Err("Mixed renderer trials in log".into());
        }
        let num = |key| {
            field(rec, key)?
                .parse::<u64>()
                .map_err(|_| format!("Invalid {key}"))
        };
        let block = num("block")?;
        let enabled: bool = field(rec, "enabled")?
            .parse()
            .map_err(|_| "Invalid enabled flag")?;
        if block != rows.len() as u64 + 1 || ORDER.get(rows.len()) != Some(&enabled) {
            return Err("Missing, duplicated or out-of-order trial block".into());
        }
        let nominal = num("block_s")?;
        let s = Sample {
            enabled,
            frames: num("frames")?,
            micros: num("interval_us")?,
            draws: num("draws")?,
            units: num(counter)?,
            kind,
        };
        if seconds.replace(nominal).is_some_and(|last| last != nominal) {
            return Err("Block duration changed during trial".into());
        }
        if nominal == 0 || s.frames == 0 || s.micros < nominal.saturating_mul(750_000) {
            return Err(format!(
                "Insufficient measured time or no accepted presents in block {block}"
            ));
        }
        if s.draws / s.frames < min_draws {
            return Err(format!(
                "Block {block} is below the draw-count threshold for this scene"
            ));
        }
        if (s.units > 0) != enabled {
            return Err(format!("Work counter disagrees with mode in block {block}"));
        }
        rows.push(s);
        if live && rows.len() == blocks {
            break;
        }
    }
    if rows.len() < blocks {
        return Err(format!(
            "Only {} of {blocks} required blocks completed",
            rows.len()
        ));
    }
    rows.truncate(blocks);
    Ok(rows)
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let usage = "usage: paired_renderer LOG|- [--blocks 4|8] [--min-draws N]";
    let path = args.next().ok_or(usage)?;
    if path == "--help" {
        println!("{usage}");
        return Ok(());
    }
    let mut blocks = 4;
    let mut min_draws = 0;
    while let Some(key) = args.next() {
        let value = args.next().ok_or(usage)?;
        match key.as_str() {
            "--blocks" => blocks = value.parse().map_err(|_| usage)?,
            "--min-draws" => min_draws = value.parse().map_err(|_| usage)?,
            _ => return Err(usage.into()),
        }
    }
    if !matches!(blocks, 4 | 8) {
        return Err(usage.into());
    }
    let samples = if path == "-" {
        collect(io::stdin().lock(), blocks, min_draws, true)?
    } else {
        collect(
            BufReader::new(File::open(path).map_err(|e| e.to_string())?),
            blocks,
            min_draws,
            false,
        )?
    };
    for enabled in [false, true] {
        let mut sum = Sample::default();
        for s in samples.iter().filter(|s| s.enabled == enabled) {
            sum.frames += s.frames;
            sum.micros += s.micros;
            sum.draws += s.draws;
            sum.units += s.units;
        }
        let name = if enabled { "on" } else { "off" };
        println!(
            "{name}: {} presents in {:.2} s, {:.2} FPS, {:.0} draws/frame, {} {}",
            sum.frames,
            sum.micros as f64 / 1e6,
            sum.fps(),
            sum.draws as f64 / sum.frames as f64,
            sum.units,
            samples[0].kind
        );
    }
    for (i, pair) in samples.chunks_exact(2).enumerate() {
        let (on, off) = if pair[0].enabled {
            (&pair[0], &pair[1])
        } else {
            (&pair[1], &pair[0])
        };
        println!(
            "Pair {}: {:+.2} FPS (on minus off)",
            i + 1,
            on.fps() - off.fps()
        );
    }
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn log() -> String {
        ORDER.iter().enumerate().map(|(i,on)| format!("\x1b[32mvictory_bench:\x1b[0m descriptor trial block={} enabled={on} frames=100 interval_us=19000000 draws=500000 cold_slots={} block_s=20\n", i + 1, u64::from(*on)*80)).collect()
    }
    #[test]
    fn balanced_orders_and_live_cutoff() {
        let log = log();
        let rows = collect(log.as_bytes(), 8, 3000, false).unwrap();
        assert!(rows.iter().map(|s| s.enabled).eq(ORDER));
        assert_eq!(collect(log.as_bytes(), 4, 3000, true).unwrap().len(), 4);
    }
    #[test]
    fn reads_a_card_sync_trial_and_rejects_a_change_of_workload() {
        let input = log()
            .replace("descriptor trial", "renderer trial kind=card_sync")
            .replace("cold_slots=", "work_units=");
        let rows = collect(input.as_bytes(), 8, 3000, false).unwrap();
        assert_eq!(rows[0].kind, "buffers batched");
        assert!(
            collect(
                input
                    .replacen("kind=card_sync", "kind=descriptors", 1)
                    .as_bytes(),
                8,
                3000,
                false
            )
            .is_err()
        );
    }
    #[test]
    fn incomplete_mixed_or_inactive_runs_are_rejected() {
        let good = log();
        for bad in [
            good.lines().take(3).collect::<Vec<_>>().join("\n"),
            format!("{good}{good}"),
            format!("{good}device removed: error"),
            good.replacen("cold_slots=0", "cold_slots=2", 1),
            good.replacen("cold_slots=80", "cold_slots=0", 1),
            good.replace("19000000", "100"),
            good.replace("draws=500000", "draws=400"),
            good.replace("frames=100", "frames=0"),
        ] {
            assert!(collect(bad.as_bytes(), 4, 3000, false).is_err());
        }
    }
}
