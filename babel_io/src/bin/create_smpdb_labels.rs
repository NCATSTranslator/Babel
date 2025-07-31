#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use polars::prelude::*;
use std::error::Error;
use std::fs;
use std::path;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    labels_output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    // NOTE: this polars implementation runs in 16ms
    let usable_columns = vec!["SMPDB ID", "Name"];

    let df = LazyCsvReader::new(options.input.clone())
        .with_infer_schema_length(Some(0))
        .with_ignore_errors(true)
        .with_truncate_ragged_lines(true)
        .with_has_header(true)
        .finish()
        .unwrap()
        .select(usable_columns.into_iter().map(|a| col(a)).collect_vec())
        .collect()
        .unwrap();

    // println!("{}", df.head(None));

    let mut labels_df = df
        .clone()
        .lazy()
        .select([concat_str([lit("SMPDB"), col("SMPDB ID")], ":", true).alias("SMPDB ID"), col("Name")])
        .collect()
        .unwrap();

    let mut file = fs::File::create(options.labels_output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut labels_df)
        .unwrap();

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
