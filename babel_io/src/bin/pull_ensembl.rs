use async_once::AsyncOnce;
use clap::Parser;
use humantime::format_duration;
use itertools::{join, Itertools};
use lazy_static::lazy_static;
use log::{debug, info};
use polars::prelude::*;
use quick_xml::Writer;
use reqwest::header;
use reqwest::redirect::Policy;
use std::collections::HashSet;
use std::error::Error;
use std::fs::{create_dir_all, File};
use std::io::{Cursor, Write};
use std::path;
use std::time::{Duration, Instant};

lazy_static! {
    pub static ref CSV_PARSE_OPTIONS: CsvParseOptions =  CsvParseOptions::default().with_truncate_ragged_lines(true).with_separator(b'\t');

    pub static ref REQWEST_CLIENT: AsyncOnce<reqwest::Client> = AsyncOnce::new(async {
        let mut headers = header::HeaderMap::new();
        // headers.insert(header::ACCEPT, header::HeaderValue::from_static("application/json"));
        headers.insert(header::CONTENT_TYPE, header::HeaderValue::from_static("text/plain"));
        let result = reqwest::Client::builder()
            .redirect(Policy::limited(5))
            // .read_timeout(Duration::from_secs(1500))
            // .timeout(Duration::from_secs(1500))
            .default_headers(headers)
            .build();

        match result {
            Ok(request_client) => request_client,
            Err(e) => panic!("Could not create reqwest client: {}", e),
        }
    });
}

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    ensembl_output_dir: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let datasets = pull_datasets().await.expect("Count not get datasets");
    debug!("datasets: {:?}", datasets);

    let usable_attribute_cols: HashSet<String> = HashSet::from([
        "ensembl_gene_id",
        "ensembl_peptide_id",
        "description",
        "external_gene_name",
        "external_gene_source",
        "external_synonym",
        "chromosome_name",
        "source",
        "gene_biotype",
        "entrezgene_id",
        "zfin_id_id",
        "mgi_id",
        "rgd_id",
        "flybase_gene_id",
        "sgd_gene",
        "wormbase_gene",
    ])
    .into_iter()
    .map(|a| a.to_string())
    .collect();

    let request_client = REQWEST_CLIENT.get().await;

    for (idx, dataset_id) in datasets.iter().enumerate() {
        let pull_dataset_start = Instant::now();
        info!("dataset_id: {}", dataset_id);

        let ensembl_output_dir = options.ensembl_output_dir.join(&dataset_id);
        create_dir_all(&ensembl_output_dir).expect("Could not create dataset dir");
        let output_path = ensembl_output_dir.join("BioMart.tsv");
        if output_path.exists() {
            continue;
        }
        let mut output_file = File::create(output_path).expect("could not create file");

        let attributes = pull_attributes(&dataset_id, &usable_attribute_cols).await.expect("Could not get attributes");
        debug!("attributes: {:?}", attributes);

        let mut writer = Writer::new(Cursor::new(Vec::new()));
        writer
            .create_element("Query")
            .with_attributes(vec![
                ("virtualSchemaName", "default"),
                ("formatter", "TSV"),
                ("header", "1"),
                ("datasetConfigVersion", "0.6"),
            ])
            .write_inner_content(|writer| {
                writer
                    .create_element("Dataset")
                    .with_attributes(vec![("name", dataset_id.as_str()), ("interface", "default")])
                    .write_inner_content(|writer| {
                        for attribute in attributes.iter() {
                            writer.create_element("Attribute").with_attribute(("name", attribute.as_str())).write_empty()?;
                        }
                        Ok(())
                    })
                    .unwrap();
                Ok(())
            })
            .unwrap();

        let xml_output = writer.into_inner().into_inner();
        let xml_result = std::str::from_utf8(xml_output.as_slice()).unwrap();
        debug!("xml result: {}", xml_result);

        let query_response = request_client
            .get("http://www.ensembl.org/biomart/martservice")
            .query(&[("query", xml_result)])
            .send()
            .await
            .expect("Could not send query");

        let query_response_text = query_response.text().await.expect("Could not get text from response");
        let handle = std::io::Cursor::new(query_response_text);
        let mut df = CsvReadOptions::default()
            .with_parse_options(CSV_PARSE_OPTIONS.clone())
            .with_has_header(true)
            .with_ignore_errors(true)
            .with_infer_schema_length(None)
            .with_low_memory(true)
            .into_reader_with_file_handle(handle)
            .finish()
            .unwrap();

        CsvWriter::new(&mut output_file)
            .include_header(true)
            .with_separator(b'\t')
            .finish(&mut df)
            .expect("Could not write Ensembl output Dataframe");

        info!(
            "dataset_id: {}, finished {}/{}, duration to pull: {}",
            dataset_id,
            idx + 1,
            datasets.len(),
            format_duration(pull_dataset_start.elapsed()).to_string()
        );
    }

    let mut w = File::create(options.ensembl_output_dir.join("BioMartDownloadComplete")).unwrap();

    writeln!(&mut w, "{}", format!("Downloaded gene sets for {} data sets.", datasets.len())).unwrap();

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}

async fn pull_datasets() -> Result<Vec<String>, Box<dyn Error>> {
    let dataset_url = "http://www.ensembl.org/biomart/martservice/biomart/martservice?type=datasets&mart=ENSEMBL_MART_ENSEMBL";

    let request_client = REQWEST_CLIENT.get().await;

    let dataset_response = request_client.get(dataset_url).send().await?;
    let dataset_text = dataset_response.text().await.unwrap();
    let filtered_data = dataset_text
        .lines()
        .filter_map(|line| if line.trim().is_empty() { None } else { Some(line.trim().to_string()) })
        .collect_vec();
    let joined_filtered_data = filtered_data.join("\n");

    let handle = Cursor::new(joined_filtered_data);
    let dataset_df = CsvReadOptions::default()
        .with_parse_options(CSV_PARSE_OPTIONS.clone())
        .with_has_header(false)
        .with_ignore_errors(true)
        .with_infer_schema_length(None)
        .into_reader_with_file_handle(handle)
        .finish()
        .unwrap();
    // println!("{}", dataset_df.head(None));

    let datasets_to_skip = join(
        &vec![
            "elucius_gene_ensembl",
            "hgfemale_gene_ensembl",
            "charengus_gene_ensembl",
            "otshawytscha_gene_ensembl",
            "aocellaris_gene_ensembl",
            "omykiss_gene_ensembl",
        ],
        "|",
    );
    let reg = format!("^({})$", datasets_to_skip);
    debug!("regex: {}", reg);

    let filtered_dataset_df = dataset_df
        .clone()
        .lazy()
        .select([col("column_2").alias("dataset_id")])
        .filter(col("dataset_id").str().contains(lit(reg), true).not())
        .collect()
        .unwrap();

    let datasets: Vec<String> = filtered_dataset_df
        .column("dataset_id")
        .unwrap()
        .str()
        .unwrap()
        .into_iter()
        .filter_map(|a| a.map(String::from))
        .collect();

    Ok(datasets)
}

async fn pull_attributes(dataset_id: &String, usable_attribute_cols: &HashSet<String>) -> Result<Vec<String>, Box<dyn Error>> {
    let request_client = REQWEST_CLIENT.get().await;
    let attributes_url = format!(
        "http://www.ensembl.org/biomart/martservice/biomart/martservice?type=attributes&dataset={}",
        dataset_id
    );

    let attributes_response = request_client.get(attributes_url).send().await?;
    let attributes_text = attributes_response.text().await.unwrap();
    let filtered_attributes_text = attributes_text
        .lines()
        .filter_map(|line| if line.trim().is_empty() { None } else { Some(line.trim().to_string()) })
        .collect_vec();
    let joined_filtered_attributes_text = filtered_attributes_text.join("\n");

    let handle = Cursor::new(joined_filtered_attributes_text);
    let attributes_df = CsvReadOptions::default()
        .with_parse_options(CSV_PARSE_OPTIONS.clone())
        .with_has_header(false)
        .with_ignore_errors(true)
        .with_infer_schema_length(None)
        .into_reader_with_file_handle(handle)
        .finish()
        .unwrap();
    // println!("{}", attributes_df.head(None));

    let filtered_attributes_df = attributes_df.clone().lazy().select([col("column_1").alias("attribute_id")]).collect().unwrap();

    let attributes: HashSet<String> = filtered_attributes_df
        .column("attribute_id")
        .unwrap()
        .str()
        .unwrap()
        .into_iter()
        .filter_map(|a| a.map(String::from))
        .collect();

    let intersection = usable_attribute_cols.intersection(&attributes).into_iter().cloned().collect_vec();

    Ok(intersection)
}
