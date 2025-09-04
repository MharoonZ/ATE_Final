import json
import os
import streamlit as st
from openai import OpenAI

from parsing import parse_query, split_options_deterministic
from prompting import normalize_options_via_llm
from effective_scraper import scrape_effective_sites


APP_TITLE = "AI System for ATE Equipment"
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4"
TEMPERATURE = 0.0


def get_openai_client() -> OpenAI:
	return OpenAI(api_key=API_KEY)


def render_message(role: str, content: str):
	if role == "user":
		st.chat_message("user").markdown(content)
	else:
		st.chat_message("assistant").markdown(content)


def _get_hardcoded_data():
	header = "quoteid	createddate	contactname	ID	record_id	createddate	QuoteID	eqModel	eqBrand	options"
	data_lines = [
		"39061	2025-08-19	Alexander Pollak	4531031	122672	NULL	39061	SMA100B	Rohde & Schwarz	B711/B86/B93/B35",
		"39019	2025-08-05	Giampiero	4530979	122599	NULL	39019	N8976B	Agilent HP Keysight	544/B25/EP5/MTU/PC7/SSD/W7X/FSA/NF2/P44/PFR/2FP/1FP/W7",
		"38804	2025-05-22	Guillermo Leon	4514403	122281	NULL	38804	4500C	BOONTON	006",
		"38713	2025-05-02	LYNN HOOVER	4469255	122154	NULL	38713	N5172B	Agilent HP Keysight	099/1EA/403/506/653/655/657/FRQ/UNV/N7631EMBC",
		"38691	2025-04-30	Mustafa Al Shaikhli	4468233	122123	NULL	38691	MS2090A	Anritsu	0031/0090/0104/0199/0714/0883/0888",
		"28871	2014-01-26	Larry Meiners	3477026	107150	NULL	28871	E4980A	Agilent	001/710/710",
		"28870	2014-01-24	Dan Hosking	3477024	107137	NULL	28870	TDS744A	Tektronix	13/1F/1M/2F",
		"28860	2014-01-23	Christopher Reinhard	3477010	107125	NULL	28860	16555D	Agilent	W Cables/Terms",
		"28861	2014-01-23	Darious Clay	3477013	107127	NULL	28861	8596E	Agilent	004/041/105/151/160",
		"27957	2013-04-12	Christopher Reinhard	3475696	105627	NULL	27957	CMU300	Rohde & Schwarz	B12/B76/B78PCMCIA/K70/K71/K75/K76/K77/K78/K79/",
		"27958	2013-04-12	David Bither	3475697	105644	NULL	27958	CMU300	Rohde & Schwarz	B11/B21/B71/K31/K32/K33/K34/K39/K41",
		"27872	2013-03-28	Sandra Fletcher	3475588	105502	NULL	27872	CMU300	Rohde & Schwarz	B21/K41/PK30",
		"27850	2013-03-25	Jeron Powell	3475561	105472	NULL	27850	33120A	Agilent / HP	/001"
	]
	return header, data_lines


def _extract_from_selected_line(header: str, line: str):
	"""Given the header and a selected raw line (tab-separated), extract eqBrand, eqModel, options."""
	# Split header to map columns
	head_cols = header.split("\t")
	col_to_idx = {name: i for i, name in enumerate(head_cols)}
	parts = line.split("\t")
	# Safely get indices
	idx_model = col_to_idx.get("eqModel")
	idx_brand = col_to_idx.get("eqBrand")
	idx_options = col_to_idx.get("options")
	brand = parts[idx_brand] if idx_brand is not None and idx_brand < len(parts) else ""
	model = parts[idx_model] if idx_model is not None and idx_model < len(parts) else ""
	options = parts[idx_options] if idx_options is not None and idx_options < len(parts) else ""
	return brand, model, options


def main():
	st.set_page_config(page_title=APP_TITLE, page_icon="🧭", layout="wide")
	st.title(APP_TITLE)
	st.caption("Select equipment from the table below and click Check to parse brand/model/options")
	
	# Get hardcoded dataset
	header, all_data_lines = _get_hardcoded_data()
	
	# Create a nice table display with selection
	if header and all_data_lines:
		st.markdown("---")
		st.subheader("📊 ATE Equipment Database")
		
		# Parse header for column names
		header_cols = header.split("\t")
		
		# Create a DataFrame-like display with selection
		st.markdown("**Select an equipment entry:**")
		
		# Create selection interface
		selected_index = st.selectbox(
			"Choose equipment:",
			options=range(len(all_data_lines)),
			format_func=lambda i: f"📋 {all_data_lines[i].split('\t')[7]} {all_data_lines[i].split('\t')[8]} - {all_data_lines[i].split('\t')[2]}",
			index=None  # No default selection
		)
		
		
		if selected_index is not None:
			selected_line = all_data_lines[selected_index]
			parts = selected_line.split("\t")
			
			
			st.markdown("---")
			st.subheader("🎯 Selected Equipment")
			
			
			col1, col2 = st.columns(2)
			with col1:
				st.markdown(f"**Quote ID:** {parts[0]}")
				st.markdown(f"**Contact:** {parts[2]}")
				st.markdown(f"**Brand:** {parts[8]}")
				st.markdown(f"**Model:** {parts[7]}")
			with col2:
				st.markdown(f"**Created:** {parts[1]}")
				st.markdown(f"**Record ID:** {parts[4]}")
				st.markdown(f"**Options:** {parts[9]}")
			
			st.markdown("---")
			check_clicked = st.button("🔍 Analyze", type="primary", use_container_width=True)
			
			if check_clicked:
				# Instant feedback
				status_placeholder = st.empty()
				status_placeholder.info("🔄 Starting analysis... Please wait.")
				
				# Extract brand/model/options from selected line
				brand, model, options_str = _extract_from_selected_line(header, selected_line)
				
				# Update status
				status_placeholder.info("🔍 Parsing equipment data...")
				
				# Use the extracted brand and model directly (no need to re-parse)
				brand_parsed = brand.strip()
				model_parsed = model.strip()
				
				# Parse options only if they exist
				if options_str:
					# Build input string for options parsing only
					user_input = f"dummy dummy /{options_str}" if not options_str.startswith("/") else f"dummy dummy {options_str}"
					parsed = parse_query(user_input)
					raw_options = parsed.get("raw_options", "").strip()
				else:
					raw_options = ""
				
				# Update status
				status_placeholder.info("🤖 Processing with AI...")
				
				
				try:
					client = get_openai_client()
					# Build input for LLM processing with correct brand/model
					llm_input = f"{brand_parsed} {model_parsed} {raw_options}" if raw_options else f"{brand_parsed} {model_parsed}"
					payload = normalize_options_via_llm(
						client,
						llm_input,
						MODEL_NAME,
						float(TEMPERATURE),
					)
					# Ensure the normalized output uses the correct brand and model
					payload["normalized"]["brand"] = brand_parsed
					payload["normalized"]["model"] = model_parsed
				except Exception as e:
					payload = {
						"normalized": {
							"brand": brand_parsed,
							"model": model_parsed,
							"options": []
						},
						"results": []
					}
					st.error(f"LLM error: {e}\nEnsure OPENAI_API_KEY is set and valid.")
				
				# Update status
				status_placeholder.info("🌐 Searching web for product information...")
				
				# Web scraping (always enabled)
				scraping_results = None
				with st.spinner("🔍 Searching for product information across multiple sources..."):
					try:
						scraping_results = scrape_effective_sites(
							brand_parsed,
							model_parsed,
							payload["normalized"]["options"]
						)
					except Exception as e:
						st.error(f"Web scraping error: {e}")
						scraping_results = None
				
				# Clear status
				status_placeholder.empty()
				
				# Display results in a nice format
				st.markdown("---")
				st.subheader("📋 Analysis Results")
				
				# Show parsing results
				st.markdown("**✅ Parsing Results:**")
				parsing_json = json.dumps(payload, indent=2)
				st.code(parsing_json, language="json")
				
				# Show scraping results
				st.markdown("**🌐 Web Scraping Results:**")
				scraping_json = {
					"web_scraping_results": []
				}
				
				if scraping_results and "search_results" in scraping_results and scraping_results["search_results"]:
					for result in scraping_results["search_results"]:
						scraping_json["web_scraping_results"].append({
							"brand": result.get('brand', 'N/A'),
							"model": result.get('model', 'N/A'),
							"price": result.get('price', 'Price not available'),
							"vendor": result.get('vendor', 'Vendor not available'),
							"web_url": result.get('web_url', 'URL not available'),
							"qty_available": result.get('qty_available', 'Quantity not available'),
							"source": result.get('source', 'Source not available')
						})
				else:
					scraping_json["web_scraping_results"] = []
				
				st.code(json.dumps(scraping_json, indent=2), language="json")
		else:
			st.info("👆 Please select an equipment entry from the dropdown above.")
	else:
		st.error("No dataset available.")


if __name__ == "__main__":
	main()


