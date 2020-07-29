install:
	pip install -e .[test]

pre-checks-deps:
	pip install flake8 "isort<5" black mypy mypy_zope

pre-checks: pre-checks-deps
	echo "TODO"
	flake8 guillotina_gcloudstorage --config=setup.cfg
	isort -c -rc guillotina_gcloudstorage
	black --check --verbose guillotina_gcloudstorage
	mypy -p guillotina_gcloudstorage --ignore-missing-imports


tests: install
	# Run tests
	pytest --capture=no --tb=native -v guillotina_gcloudstorage
