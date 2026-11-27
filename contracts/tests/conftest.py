import sys
import types

try:
    import confluent_kafka  # noqa: F401
except ImportError:
    fake = types.ModuleType("confluent_kafka")

    class KafkaError:
        _PARTITION_EOF = -191

    class KafkaException(Exception):
        pass

    class TopicPartition:
        def __init__(self, topic, partition=0, offset=-1001):
            self.topic = topic
            self.partition = partition
            self.offset = offset

    class Consumer:
        def __init__(self, config):
            self.config = config

    fake.KafkaError = KafkaError
    fake.KafkaException = KafkaException
    fake.TopicPartition = TopicPartition
    fake.Consumer = Consumer
    sys.modules["confluent_kafka"] = fake