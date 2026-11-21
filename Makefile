KIT := .cache/mechfight-kit
CHECK := $(KIT)/check/check.py
URL := https://www.joinbuilders.org/buildathon/tracks/builders/files/mechfight-kit.tar.gz
SHA := 1758fe9125e193b268c6c1cffbf2c0ae96377214ab06d117412571c1523065ba

.PHONY: check check-docker
check: $(CHECK)
	python3 $(CHECK) --map-dir $(KIT)/arena -- python3 -u bot.py

check-docker: $(CHECK)
	docker build --platform linux/amd64 -t buildathon-mech .
	python3 $(CHECK) --map-dir /arena -- docker run -i --rm --platform linux/amd64 --network none --cpus 1 --memory 512m --read-only --tmpfs /tmp:rw,size=64m --user 65534:65534 -v "$(CURDIR)/$(KIT)/arena:/arena:ro" buildathon-mech

$(CHECK):
	mkdir -p .cache
	curl -fsSL --retry 3 "$(URL)" -o .cache/mechfight.tar.gz
	python3 -c "import hashlib, pathlib, sys; sys.exit(hashlib.sha256(pathlib.Path('.cache/mechfight.tar.gz').read_bytes()).hexdigest() != '$(SHA)')"
	tar -xzf .cache/mechfight.tar.gz -C .cache
