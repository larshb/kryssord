all: js/material.min.js css/material.brown-amber.min.css

DOWNLOAD = curl --create-dirs

js/material.min.js:
	$(DOWNLOAD) -o $@ https://cdn.jsdelivr.net/npm/material-design-lite@1.3.0/material.min.js

css/material.brown-amber.min.css:
	$(DOWNLOAD) -o $@ https://cdnjs.cloudflare.com/ajax/libs/material-design-lite/1.3.0/material.brown-amber.min.css
