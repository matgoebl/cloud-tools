from yapsy.IPlugin import IPlugin
import os
import logging
import fastavro
import io

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
        #schema_name = raw_payload[1:schema_name_len+1]
        #raw_payload = raw_payload[schema_name_len+1:]

        # Lazy load schemas once when they are used first:
        if not schema_name in self.schemas:
            try:
                logging.debug(f"Loading AVRO schema {schema_name}...")
                self.schemas[schema_name] = fastavro.schema.load_schema( os.path.join(self.schemas_path, schema_name + ".avsc"))
            except:
                logging.warn(f"Cannot load AVRO schema for {schema_name}...")
                self.schemas[schema_name] = None

        if not self.schemas[schema_name]:
            return None
            
        try:
            decoded_payload = fastavro.schemaless_reader(io.BytesIO(raw_payload), self.schemas[schema_name])
            return decoded_payload
        except:
            logging.warn(f"Cannot decode AVRO message with schema {schema_name}")
            return None
