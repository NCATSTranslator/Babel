#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use std::error::Error;
use std::fs;
use std::fs::File;
use std::io::{BufRead, Write};
use std::path;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    sprot_input: path::PathBuf,

    #[clap(short, long, required = true)]
    trembl_input: path::PathBuf,

    #[clap(short, long, required = true)]
    output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let mut writer = std::io::BufWriter::new(fs::File::create(options.output.clone().as_path()).unwrap());

    write_labels(&mut writer, options.sprot_input, "sprot".into()).unwrap();
    write_labels(&mut writer, options.trembl_input, "trembl".into()).unwrap();

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}

fn write_labels(writer: &mut std::io::BufWriter<File>, input: path::PathBuf, which: String) -> Result<(), Box<dyn Error>> {
    let reader = std::io::BufReader::new(fs::File::open(input).unwrap());
    for line in reader.lines() {
        let line = line.unwrap();
        if !line.starts_with(">") {
            continue;
        }

        let line_split = line.split('|').collect_vec();
        let name_split = line_split.get(2).unwrap().split(" OS=").collect_vec();
        write!(writer, "UniProtKB:{}\t{} ({})\n", line_split.get(1).unwrap(), name_split.get(0).unwrap(), which).unwrap();
    }
    Ok(())
}

