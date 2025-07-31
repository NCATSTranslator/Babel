#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use polars::frame::DataFrame;
use polars::io::SerWriter;
use polars::prelude::*;
use std::error::Error;
use std::fs;
use std::path;
use std::path::PathBuf;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    labels_output: path::PathBuf,

    #[clap(short, long, required = true)]
    synonyms_output: path::PathBuf,

    #[clap(short, long, required = true)]
    taxa_output: path::PathBuf,

    #[clap(short, long, required = true)]
    description_output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    // let br = BufReader::new(fs::File::open(options.input).unwrap());

    // let mut labels_bw = std::io::BufWriter::new(fs::File::create(options.labels_output.as_path()).unwrap());
    // let mut synonyms_bw = std::io::BufWriter::new(fs::File::create(options.synonyms_output.as_path()).unwrap());
    // let mut taxa_bw = std::io::BufWriter::new(fs::File::create(options.taxa_output.as_path()).unwrap());
    // let mut description_bw = std::io::BufWriter::new(fs::File::create(options.description_output.as_path()).unwrap());

    let usable_columns = vec![
        "#tax_id",
        "GeneID",
        "type_of_gene",
        "Synonyms",
        "Other_designations",
        "Symbol_from_nomenclature_authority",
        "Full_name_from_nomenclature_authority",
        "Symbol",
        "description",
    ];

    let df = polars::lazy::frame::LazyCsvReader::new(options.input.clone())
        .with_separator(b'\t')
        .with_infer_schema_length(Some(0))
        .with_ignore_errors(true)
        .with_truncate_ragged_lines(true)
        .with_has_header(true)
        .finish()
        .unwrap()
        .select(usable_columns.into_iter().map(|a| col(a)).collect_vec())
        .filter(col("type_of_gene").str().contains(lit("^(biological-region|other|unknown)$"), true).not())
        .with_column(concat_str([lit("NCBIGene"), col("GeneID")], ":", true).alias("GeneID"))
        .with_column(concat_str([lit("NCBITaxon"), col("#tax_id")], ":", true).alias("#tax_id"))
        .with_column(
            concat_str(
                [
                    col("Full_name_from_nomenclature_authority"),
                    col("Synonyms"),
                    col("Other_designations"),
                    col("Symbol_from_nomenclature_authority"),
                    col("Symbol"),
                ],
                "|",
                true,
            )
            .str()
            .split(lit("|"))
            .alias("synonyms_concat"),
        )
        .with_column(
            col("synonyms_concat")
                .list()
                .eval(col("").filter(col("").is_in(lit("-")).not()), false)
                .alias("synonyms_concat"),
        )
        // .drop([col("Full_name_from_nomenclature_authority"), col("Other_designations")])
        .collect()
        .unwrap();

    debug!("shape: {:?}", df.shape());

    // NOTE: python impl runs in 13m w/ streaming, rust runs in < 3m while holding data in memory
    // TODO: these could be async & run in parallel
    write_description(&df, &options.description_output);
    write_taxa(&df, &options.taxa_output);
    write_synonyms(&df, &options.synonyms_output);
    write_labels(&df, &options.labels_output);

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}

fn write_synonyms(df: &DataFrame, output: &PathBuf) {
    let mut tmp_df = df
        .clone()
        .lazy()
        .select([
            col("GeneID"),
            lit("http://www.geneontology.org/formats/oboInOwl#hasSynonym"),
            col("synonyms_concat"),
        ])
        .explode([col("synonyms_concat")])
        .collect()
        .unwrap();

    // println!("{}", tmp_df.head(None));

    let mut file = fs::File::create(output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut tmp_df)
        .unwrap();
}

fn write_description(df: &DataFrame, output: &PathBuf) {
    let mut tmp_df = df.clone().lazy().select([col("GeneID"), col("description")]).collect().unwrap();

    // println!("{}", tmp_df.head(None));

    let mut file = fs::File::create(output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut tmp_df)
        .unwrap();
}

fn write_labels(df: &DataFrame, output: &PathBuf) {
    let mut tmp_df = df
        .clone()
        .lazy()
        .with_column(
            when(
                col("Symbol_from_nomenclature_authority")
                    .is_null()
                    .or(col("Symbol_from_nomenclature_authority").eq(lit("-"))),
            )
            .then(col("Symbol"))
            .otherwise(col("Symbol_from_nomenclature_authority"))
            .alias("best_symbol"),
        )
        .with_column(
            when(col("best_symbol").is_null().and(col("synonyms_concat").list().len().gt(0)))
                .then(col("synonyms_concat").list().first())
                .otherwise(col("best_symbol")),
        )
        .select([col("GeneID"), col("best_symbol")])
        .collect()
        .unwrap();

    // println!("{}", tmp_df.head(None));

    let mut file = fs::File::create(output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut tmp_df)
        .unwrap();
}

fn write_taxa(df: &DataFrame, output: &path::PathBuf) {
    let mut tmp_df = df.clone().lazy().select([col("GeneID"), col("#tax_id")]).collect().unwrap();

    // println!("{}", tmp_df.head(None));

    let mut file = fs::File::create(output).expect("could not create file");
    CsvWriter::new(&mut file)
        .include_header(false)
        .with_separator(b'\t')
        .finish(&mut tmp_df)
        .unwrap();
}
