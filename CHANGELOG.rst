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
