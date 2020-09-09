install:
	pip install -e .[test]

pre-checks-deps: lint-deps
	# pip install flake8 mypy_zope "mypy<0.782"
	echo ""

pre-checks: pre-checks-deps
	# flake8 guillotina_gcloudstorage --config=setup.cfg
	cat setup.cfg
	isort -v
	pip list
	isort --diff -rc guillotina_gcloudstorage
	isort -c -rc guillotina_gcloudstorage
	# black --check --verbose guillotina_gcloudstorage
	#mypy -p guillotina_gcloudstorage --ignore-missing-imports

lint-deps:
	#pip install -U "isort>=4,<5" toml==0.10.1
	pip install 'git+https://github.com/PyCQA/isort.git@4.3.21-2'
	#black

lint:
	isort -rc guillotina_gcloudstorage
	black guillotina_gcloudstorage


tests: install
	# Run tests
	pytest --capture=no --tb=native -v guillotina_gcloudstorage
