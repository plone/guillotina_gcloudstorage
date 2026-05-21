GUILLOTINA_GCLOUDSTORAGE
========================

Google Cloud Storage blob storage for Guillotina 7.


Example config.json entry:

.. code-block:: json

    ...
    "cloud_storage": "guillotina_gcloudstorage.interfaces.IGCloudFileField",
    "cloud_datamanager": "redis",
    "load_utilities": {
        "gcloud": {
            "provides": "guillotina_gcloudstorage.interfaces.IGCloudBlobStore",
            "factory": "guillotina_gcloudstorage.storage.GCloudBlobStore",
            "settings": {
                "uniform_bucket_level_access": True,
                "json_credentials": "/path/to/credentials.json",
                "bucket": "name-of-bucket",
                "project": "name-of-project",
                "bucket_name_format": "{container}-foobar{delimiter}{base}",
                "bucket_labels": {
                    "foo": "bar"
                }
            }
        }
    }
    ...


Getting started with development
--------------------------------

Using pip (requires Python 3.10 or newer):

.. code-block:: shell

    python3.10 -m venv .
    ./bin/pip install -e .[test]
    pre-commit install


Running tests
-------------

The test suite uses a Google Cloud Storage bucket. Configure these environment
variables before running it:

.. code-block:: shell

    export GCLOUD_CREDENTIALS=/absolute/path/to/google-cloud-service-account.json
    export GCLOUD_BUCKET=name-of-test-bucket
    export GCLOUD_PROJECT=name-of-project
    make tests

