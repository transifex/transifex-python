CUR_PATH=$(shell pwd)

build:
	DOCKER_BUILDKIT=1 docker build \
		--no-cache \
		--progress=plain \
		--build-arg PYTHON_VERSION=2.7 \
		--build-arg DJANGO_VERSION=1.11 \
		-t native:2.7-1.11-latest \
		-f Dockerfile-tmpl .
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.6 \
	        --build-arg DJANGO_VERSION=1.11 \
	        -t native:3.6-1.11-latest \
	        -f Dockerfile-tmpl .

localtests:
	docker run -it \
	    -v $(CUR_PATH):/usr/app \
	    --rm native:2.7-1.11-latest\
	    pytest --cov --cov-append --cov-report=term-missing
	docker run -it \
	    -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest\
	    pytest --cov --cov-append --cov-report=term-missing
	docker run -it \
	    -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest \
	    coverage report -m
