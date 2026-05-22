install:
	pip install -e .[test]

pre-checks-deps: lint-deps
	pip install "flake8==7.3.0" "mypy==2.1.0" "mypy-zope==1.0.15"

pre-checks: pre-checks-deps
	flake8 guillotina_gcloudstorage --config=setup.cfg
	isort --check-only guillotina_gcloudstorage
	black --check --verbose guillotina_gcloudstorage
	mypy -p guillotina_gcloudstorage --ignore-missing-imports

lint-deps:
	pip install "isort==8.0.1" "black==26.5.1"

lint:
	isort guillotina_gcloudstorage
	black guillotina_gcloudstorage


tests: install
	# Run tests
	pytest --capture=no --tb=native -v guillotina_gcloudstorage
