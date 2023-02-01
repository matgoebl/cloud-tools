from yapsy.IPlugin import IPlugin
import os
import logging
import fastavro
import io
import zlib
import uuid

class AvroPlugin(IPlugin):
    def __init__(self):
        logging.debug(f"Initializing AVRO plugin...")
        self.schemas_path = os.environ.get('AVSC_PATH','.')
        self.schemas = {}

    def decode(self, raw_payload, topic):
        # in this example the schema name is derived from the topic name:
        schema_name = topic

        # another example, where the schema name is prepended to the real payload:
        #schema_name_len = raw_payload[0]
        #schema_name = raw_payload[1:schema_name_len+1].decode()
        #raw_payload = raw_payload[schema_name_len+1:]

        # for using the AWS Glue Schema Registry with the Java Client:
        # the encoding is implemented here: https://github.com/awslabs/aws-glue-schema-registry/blob/master/serializer-deserializer/src/main/java/com/amazonaws/services/schemaregistry/serializers/SerializationDataEncoder.java
        # the constants can be found here: https://github.com/awslabs/aws-glue-schema-registry/blob/master/common/src/main/java/com/amazonaws/services/schemaregistry/utils/AWSSchemaRegistryConstants.java
        # inspired also from: https://github.com/DisasterAWARE/aws-glue-schema-registry-python/blob/main/src/aws_schema_registry/codec.py
        header_version_byte = int(raw_payload[0])
        compression_type_byte = int(raw_payload[1])
        schema_version_id = str(uuid.UUID(bytes=raw_payload[2:18]))
        HEADER_VERSION_GLUE = 3
        COMPRESSION_TYPE_ZLIB = 5
        if header_version_byte == HEADER_VERSION_GLUE:
            if compression_type_byte == COMPRESSION_TYPE_ZLIB:
                raw_payload = zlib.decompress(raw_payload[18:])
            else:
                raw_payload = raw_payload[18:]
            schema_name = topic + "." + schema_version_id

        # Lazy load schemas once on their first use:
        if not schema_name in self.schemas:
            try:
                logging.debug(f"Loading AVRO schema {schema_name}...")
                self.schemas[schema_name] = fastavro.schema.load_schema( os.path.join(self.schemas_path, schema_name + ".avsc"))
            except:
                logging.warn(f"Cannot load AVRO schema for {schema_name}")
                self.schemas[schema_name] = None

        if not self.schemas[schema_name]:
            return None
            
        try:
            decoded_payload = fastavro.schemaless_reader(io.BytesIO(raw_payload), self.schemas[schema_name])
            return decoded_payload
        except:
            logging.warn(f"Cannot decode AVRO message with schema {schema_name}")
            return None
