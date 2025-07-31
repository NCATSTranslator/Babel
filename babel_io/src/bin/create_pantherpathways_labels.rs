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

    // PANTHER.PATHWAY:P06217	Toll pathway-drosophila
    // P06217	Toll pathway-drosophila	P06348	SLMB	DROME|FlyBase=FBgn0283468|UniProtKB=A0A0B4KHK1	Supernumerary limbs, isoform B	IDA	9461217	PubMed	PTHR44156:SF29	TNF RECEPTOR ASSOCIATED FACTOR 7

    // NOTE: this polars implementation runs in 16ms

    let usable_columns = vec!["I", "II"];

    let schema = Schema::from_iter(vec![
        Field::new("I".into(), DataType::String),
        Field::new("II".into(), DataType::String),
        Field::new("III".into(), DataType::String),
        Field::new("IV".into(), DataType::String),
        Field::new("V".into(), DataType::String),
        Field::new("VI".into(), DataType::String),
        Field::new("VII".into(), DataType::String),
        Field::new("VIII".into(), DataType::String),
        Field::new("IX".into(), DataType::String),
        Field::new("X".into(), DataType::String),
        Field::new("XI".into(), DataType::String),
    ]);

    let df = LazyCsvReader::new(options.input.clone())
        .with_separator(b'\t')
        .with_schema(Some(schema.into()))
        .with_ignore_errors(true)
        .with_truncate_ragged_lines(true)
        .with_has_header(false)
        .finish()
        .unwrap()
        .select(usable_columns.into_iter().map(|a| col(a)).collect_vec())
        .collect()
        .unwrap();

    // println!("{}", df.head(None));

    let mut labels_df = df
        .clone()
        .lazy()
        .select([concat_str([lit("PANTHER.PATHWAY"), col("I")], ":", true).alias("I"), col("II")])
        .unique(Some(vec!["I".into(), "II".into()]), UniqueKeepStrategy::First)
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
