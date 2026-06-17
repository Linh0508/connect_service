#!/bin/bash
# Script tạo các topic cần thiết cho B6

echo "========================================="
echo "  Creating Kafka Topics for B6"
echo "========================================="

# Đợi Kafka sẵn sàng
echo "Waiting for Kafka to be ready..."
sleep 10

# Tạo topic notification.alerts
docker exec b6-kafka kafka-topics --create \
  --if-not-exists \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 1 \
  --topic notification.alerts

if [ $? -eq 0 ]; then
  echo "✅ Topic 'notification.alerts' created"
else
  echo "❌ Failed to create topic 'notification.alerts'"
fi

# Tạo topic analytics.decisions
docker exec b6-kafka kafka-topics --create \
  --if-not-exists \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 1 \
  --topic analytics.decisions

if [ $? -eq 0 ]; then
  echo "✅ Topic 'analytics.decisions' created"
else
  echo "❌ Failed to create topic 'analytics.decisions'"
fi

# Liệt kê tất cả topic
echo ""
echo "📋 Existing topics:"
docker exec b6-kafka kafka-topics --list --bootstrap-server localhost:9092

echo ""
echo "========================================="
echo "  Setup complete!"
echo "========================================="
