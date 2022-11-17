CUR_PATH=$(shell pwd)
FILES=$(shell git ls-files transifex* tests*)

build:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.6 \
	        --build-arg DJANGO_VERSION=1.11 \
	        -t native:3.6-1.11-latest \
	        -f Dockerfile-tmpl .
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.6 \
	        --build-arg DJANGO_VERSION=2.0 \
	        -t native:3.6-2.0-latest \
	        -f Dockerfile-tmpl .
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.8 \
	        --build-arg DJANGO_VERSION=2.2 \
	        -t native:3.8-2.2-latest \
	        -f Dockerfile-tmpl .
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.9 \
	        --build-arg DJANGO_VERSION=3.2 \
	        -t native:3.9-3.2-latest \
	        -f Dockerfile-tmpl .

code_quality:
	git diff origin/devel..$(git rev-parse HEAD) --name-only | \
        xargs docker run --rm \
            --user $$(id -u):$$(id -g) \
            --mount src="$$(pwd)",target=/src,type=bind \
            transifex/txlint --files

shell_dj1.11_py3.6:
	# Django 1.11 (3.6)
	docker run --rm -it --entrypoint bash native:3.6-1.11-latest

shell_dj2.0_py3.6:
	# Django 2.0 (Python 3.6)
	docker run --rm -it --entrypoint bash native:3.6-2.0-latest

shell_dj2.2_py3.8:
	# Django 2.2 (Python 3.8)
	docker run --rm -it --entrypoint bash native:3.8-2.2-latest

shell_dj3.2_py3.9:
	# Django 3.2 (Python 3.9)
	docker run --rm -it --entrypoint bash native:3.9-3.2-latest

localtests:
	# Django 1.11 (3.6)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest\
	    pytest --cov --cov-append --cov-report=term-missing

	# Django 2.0 (Python 3.6)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-2.0-latest\
	    pytest --cov --cov-append --cov-report=term-missing

	# Django 2.2 (Python 3.8)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.8-2.2-latest\
	    pytest --cov --cov-append --cov-report=term-missing

	# Django 3.2 (Python 3.9)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.9-3.2-latest\
	    pytest --cov --cov-append --cov-report=term-missing

	# Coverage report
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest \
	    coverage report -m
