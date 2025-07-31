#[macro_use]
extern crate log;

use clap::Parser;
use humantime::format_duration;
use itertools::Itertools;
use oxigraph::io::RdfFormat;
use oxigraph::sparql::QueryResults;
use oxigraph::store::Store;
use std::error::Error;
use std::fs;
use std::io;
use std::io::Write;
use std::path;
use std::time::Instant;

#[derive(Parser, PartialEq, Debug)]
#[clap(author, version, about, long_about = None)]
struct Options {
    #[clap(short, long, required = true)]
    input: path::PathBuf,

    #[clap(short, long, required = true)]
    output: path::PathBuf,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let start = Instant::now();
    env_logger::init();

    let options = Options::parse();
    debug!("{:?}", options);

    let br = io::BufReader::new(fs::File::open(options.input).unwrap());
    let store = Store::new()?;
    let start_load = Instant::now();
    store
        .bulk_loader()
        .with_max_memory_size_in_megabytes(4 * 2048)
        .with_num_threads(4)
        .load_from_reader(RdfFormat::NTriples, br)
        .expect("Could not load input");
    info!("duration to load input: {}", format_duration(start_load.elapsed()).to_string());

    let mut output_bw = std::io::BufWriter::new(fs::File::create(options.output.clone().as_path()).unwrap());

    let re = regex::Regex::new("^(.*?)(?:@[^@]*){0,1}$").unwrap();

    let query_statement = r#"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
             PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
             PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

             SELECT DISTINCT ?term ?label WHERE { ?term rdfs:label ?label } ORDER BY ?term"#;

    if let QueryResults::Solutions(solutions) = store.query(query_statement)? {
        for qs in solutions.filter_map(Result::ok).into_iter() {
            let term = qs.get("term").expect("term was None");
            let mut term = term.to_string();
            term = babel_io::trim_gt_and_lt(term);
            let term_split = term.split("/").collect_vec();
            let id = term_split.last().unwrap();

            let label = qs.get("label").expect("x was None");
            let mut label = label.to_string();
            if label.contains("@") {
                if let Some(captures) = re.captures(label.as_str()) {
                    label = captures.get(1).unwrap().as_str().to_string();
                }
            }
            label = babel_io::trim_quotes(label);
            label = label.trim().to_string();

            write!(output_bw, "MESH:{}\t{}\n", id, label).expect("Could not write triple");
        }
    }

    info!("Duration: {}", format_duration(start.elapsed()).to_string());
    Ok(())
}
