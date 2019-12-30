from guillotina import testing

import os


def base_settings_configurator(settings):
    if "applications" in settings:
        settings["applications"].append("guillotina_gcloudstorage")
    else:
        settings["applications"] = ["guillotina_gcloudstorage"]

    settings["load_utilities"]["gcloud"] = {
        "provides": "guillotina_gcloudstorage.interfaces.IGCloudBlobStore",
        "factory": "guillotina_gcloudstorage.storage.GCloudBlobStore",
        "settings": {
            "json_credentials": os.environ["GCLOUD_CREDENTIALS"],
            "bucket": os.environ["GCLOUD_BUCKET"],
            "project": os.environ["GCLOUD_PROJECT"],
            "bucket_name_format": "{container}-foobar{delimiter}{base}",
            "bucket_labels": {"foo": "bar"},
        },
    }


testing.configure_with(base_settings_configurator)
