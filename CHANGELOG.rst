2.0.0 (2018-06-07)
------------------

- Upgrade to guillotina 4
  [vangheem]


1.1.7 (2018-06-07)
------------------

- Pin version of guillotina
  [vangheem]


1.1.6 (2018-06-07)
------------------

- Handle 404 when copying files
  [vangheem]


1.1.5 (2018-05-12)
------------------

- bump


1.1.4 (2018-05-12)
------------------

- More strict object checks
  [vangheem]


1.1.3 (2018-03-20)
------------------

- Another logging fix
  [vangheem]


1.1.2 (2018-03-20)
------------------

- Fix logging issue
  [vangheem]


1.1.1 (2018-03-19)
------------------

- Be able to use `iter_data` with custom uri
  [vangheem]


1.1.0 (2018-03-19)
------------------

- Upgrade to latest guillotina file management to simplify code-base
  [vangheem]


1.0.36 (2018-03-09)
-------------------

- Fix saving previous file
  [vangheem]


1.0.35 (2018-03-01)
-------------------

- Change when we store previous file info
  [vangheem]


1.0.34 (2018-02-22)
-------------------

- Customize more of the download
  [vangheem]


1.0.33 (2018-02-22)
-------------------

- Be able to specify uri to download
  [vangheem]


1.0.32 (2018-02-21)
-------------------

- Tweak IFileCleanup
  [vangheem]


1.0.31 (2018-02-20)
-------------------

- Implement IFileCleanup
  [vangheem]


1.0.30 (2018-01-02)
-------------------

- Retry google cloud exceptions
  [vangheem]


1.0.29 (2017-10-30)
-------------------

- Handle file size being zero for download reporting
  [vangheem]


1.0.28 (2017-10-12)
-------------------

- Make sure to register write on object for behavior files
  [vangheem]


1.0.27 (2017-10-11)
-------------------

- Return NotFound response when no file found on context
  [vangheem]


1.0.26 (2017-10-04)
-------------------

- Handle google cloud error when deleting existing files
  [vangheem]


1.0.25 (2017-10-03)
-------------------

- Check type instead of None for existing value
  [vangheem]


1.0.24 (2017-10-02)
-------------------

- Use latest guillotina base classes
  [vangheem]

- Use field context if set
  [vangheem]


1.0.23 (2017-10-02)
-------------------

- Add copy_cloud_file method
  [vangheem]


1.0.22 (2017-09-29)
-------------------

- Limit request limit cache size to a max of the CHUNK_SIZE
  [vangheem]


1.0.21 (2017-09-29)
-------------------

- Cache data on request object in case of request conflict errors
  [vangheem]


1.0.20 (2017-09-27)
-------------------

- Do not timeout when downloading for gcloud
  [vangheem]

- Make sure to use async with syntax with aiohttp requests
  [vangheem]


1.0.19 (2017-09-11)
-------------------

- Make sure CORS headers are applied before we start sending a download result
  [vangheem]


1.0.18 (2017-09-11)
-------------------

- Be able to override disposition of download
  [vangheem]


1.0.17 (2017-09-01)
-------------------

- Implement save_file method
  [vangheem]


1.0.16 (2017-08-15)
-------------------

- Provide iter_data method
  [vangheem]


1.0.15 (2017-06-15)
-------------------

- Guess content type if none provided when downloading file
  [vangheem]


1.0.14 (2017-06-14)
-------------------

- Be able to customize content disposition header of file download
  [vangheem]


1.0.13 (2017-06-12)
-------------------

- Remove GCloudBlobStore._service property
  [vangheem]

- Change GCloudBlobStore._bucket to GCloudBlobStore._bucket_name
  [vangheem]

- Remove GCloudBlobStore._client property
  [vangheem]

- Rename GCloudBlobStore.bucket property to coroutine:GCloudBlobStore.get_bucket_name()
  [vangheem]

- Make everything async and use executor if necessary so we don't block
  [vangheem]


1.0.12 (2017-05-19)
-------------------

- Provide iterate_bucket method
  [vangheem]


1.0.11 (2017-05-19)
-------------------

- provide method to rename object
  [vangheem]

- Use keys that use the object's oid
  [vangheem]

- Make delete async
  [vangheem]


1.0.10 (2017-05-02)
-------------------

- Convert bytes to string for content_type
  [vangheem]


1.0.9 (2017-05-02)
------------------

- contentType was renamed to content_type
  [vangheem]


1.0.8 (2017-05-02)
------------------

- Make sure to register the object for writing to the database
  [vangheem]


1.0.7 (2017-05-01)
------------------

- Fix reference to _md5hash instead of _md5 so serializing works
  [vangheem]


1.0.6 (2017-05-01)
------------------

- Fix bytes serialization issue
  [vangheem]


1.0.5 (2017-05-01)
------------------

- Fix import error
  [vangheem]


1.0.4 (2017-05-01)
------------------

- Do not inherit from BaseObject
  [vangheem]


1.0.3 (2017-05-01)
------------------

- Allow GCloudFile to take all arguments
  [vangheem]


1.0.2 (2017-04-26)
------------------

- Need to be able to provide loop param in constructor of utility
  [vangheem]


1.0.1 (2017-04-25)
------------------

- Compatibility fixes with aiohttp 2
  [vangheem]


1.0.0 (2017-04-24)
------------------

- initial release
