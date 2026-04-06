PYTHON ?= python

.PHONY: install install-preprocess editable test app qa fetch process worldview

install:
	$(PYTHON) -m pip install -r requirements.txt

install-preprocess:
	$(PYTHON) -m pip install -r requirements-preprocess.txt

editable:
	$(PYTHON) -m pip install -e .

test:
	pytest -q

app:
	streamlit run app.py

fetch:
	$(PYTHON) fetch_banciu_videos.py

qa:
	$(PYTHON) process_banciu_transcripts.py --qa-only

process:
	$(PYTHON) process_banciu_transcripts.py

worldview:
	$(PYTHON) extract_worldview.py

