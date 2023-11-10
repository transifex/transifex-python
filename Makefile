CUR_PATH=$(shell pwd)
FILES=$(shell git ls-files transifex* tests*)

# --- Build ---

build: \
	build_dj1.11_py3.6 \
	build_dj2.0_py3.6 \
	build_dj2.2_py3.8 \
	build_dj3.2_py3.9 \
	build_dj4.1_py3.11 \
	build_dj4.2_py3.12

build_dj1.11_py3.6:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.6 \
	        --build-arg DJANGO_VERSION=1.11 \
	        -t native:3.6-1.11-latest \
	        -f Dockerfile-tmpl .

build_dj2.0_py3.6:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.6 \
	        --build-arg DJANGO_VERSION=2.0 \
	        -t native:3.6-2.0-latest \
	        -f Dockerfile-tmpl .

build_dj2.2_py3.8:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.8 \
	        --build-arg DJANGO_VERSION=2.2 \
	        -t native:3.8-2.2-latest \
	        -f Dockerfile-tmpl .

build_dj3.2_py3.9:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.9 \
	        --build-arg DJANGO_VERSION=3.2 \
	        -t native:3.9-3.2-latest \
	        -f Dockerfile-tmpl .

build_dj4.1_py3.11:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.11 \
	        --build-arg DJANGO_VERSION=4.1 \
	        -t native:3.11-4.1-latest \
	        -f Dockerfile-tmpl .

build_dj4.2_py3.12:
	DOCKER_BUILDKIT=1 docker build \
	        --no-cache \
	        --progress=plain \
	        --build-arg PYTHON_VERSION=3.12 \
	        --build-arg DJANGO_VERSION=4.2 \
	        -t native:3.12-4.2-latest \
	        -f Dockerfile-tmpl .

# --- Code quality ---

code_quality:
	git diff origin/devel..$(git rev-parse HEAD) --name-only | \
        xargs docker run --rm \
            --user $$(id -u):$$(id -g) \
            --mount src="$$(pwd)",target=/src,type=bind \
            transifex/txlint --files

# --- Shell ---

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

shell_dj4.1_py3.11:
	# Django 4.1 (Python 3.11)
	docker run --rm -it --entrypoint bash native:3.11-4.1-latest

shell_dj4.2_py3.12:
	# Django 4.2 (Python 3.12)
	docker run --rm -it --entrypoint bash native:3.12-4.2-latest

# --- Tests ---

localtests: \
	tests_dj1.11_py3.6 \
	tests_dj2.0_py3.6 \
	tests_dj2.2_py3.8 \
	tests_dj3.2_py3.9 \
	tests_dj4.1_py3.11 \
	tests_dj4.2_py3.12 \
	tests_coverage

tests_dj1.11_py3.6:
	# Django 1.11 (3.6)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_dj2.0_py3.6:
	# Django 2.0 (Python 3.6)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-2.0-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_dj2.2_py3.8:
	# Django 2.2 (Python 3.8)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.8-2.2-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_dj3.2_py3.9:
	# Django 3.2 (Python 3.9)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.9-3.2-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_dj4.1_py3.11:
	# Django 4.1 (Python 3.11)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.11-4.1-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_dj4.2_py3.12:
	# Django 4.2 (Python 3.12)
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.12-4.2-latest\
	    pytest --cov --cov-append --cov-report=term-missing

tests_coverage:
	# Coverage report
	docker run -v $(CUR_PATH):/usr/app \
	    --rm native:3.6-1.11-latest \
	    coverage report -m
