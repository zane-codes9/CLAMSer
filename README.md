# CLAMSer: Analysis in Three Steps

[![Status](https://img.shields.io/badge/Status-Beta-orange.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.33+-ff4b4b.svg)](https://streamlit.io)

CLAMSer is an open-source tool for automating metabolic data processing from Columbus Instruments CLAMS systems.

**[➡️ Live Application](https://clamser.streamlit.app/)**

**[▶️ Video Walkthrough](https://www.youtube.com/watch?v=LuBnGmRzcB8)**

---

(placeholder - flowchart showing CLAMSer flow coming soon)
![CLAMSer Workflow GIF](https://github.com/Zane-K/CLAMSer/blob/main/assets/clamser_demo.gif?raw=true)

## Features of CLAMSer

* Upload all your raw `.csv` files at once (batch processing)
* Analyze entire dataset or use presets for the last 24/48/72 hours, or custom window.
* Define experimental groups 
* Switch results view between **Absolute**, **Body Weight Normalized**, and **Lean Mass Normalized** values.
* Visualize timeline charts (color-coded by group) and summary bar charts.
* Download summary CSV files ready for statistical software (SPSS, Jamovi, GraphPad Prism).

## Cite

This tool is currently under beta-testing. For now, please cite this tool by name (CLAMSer) and link to its hosted location (https://clamser.streamlit.app/). A formal manuscript describing CLAMSer is in preparation.

## Feedback & Contributing

This is a beta release. For questions, bug reports, or feature suggestions, please email me (Zane) at `mkhal061@uottawa.ca` or open an issue on this repo.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Local Installation

Here's how to run CLAMSer on your local machine (terminal):

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/zane-codes9/CLAMSer.git
    cd CLAMSer
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```
