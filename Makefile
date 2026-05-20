install:
	pip install -e .[test]

pre-checks-deps: lint-deps
	pip install flake8 "mypy==1.15.0" "mypy-zope==1.0.11"

pre-checks: pre-checks-deps
	flake8 guillotina_gcloudstorage --config=setup.cfg
	isort --check-only guillotina_gcloudstorage
	black --check --verbose guillotina_gcloudstorage
	mypy -p guillotina_gcloudstorage --ignore-missing-imports

lint-deps:
	pip install "isort==5.13.2" "black==24.10.0"

lint:
	isort guillotina_gcloudstorage
	black guillotina_gcloudstorage


tests: install
	# Run tests
	pytest --capture=no --tb=native -v guillotina_gcloudstorage
