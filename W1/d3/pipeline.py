import logging
import queue
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class Config:
    CSV_URL = (
        "https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/machine_temperature_system_failure.csv"
    )
    CSV_PATH = Path("machine_temperature_system_failure.csv")
    PARQUET_OUTPUT = Path("features.parquet")
    JSON_OUTPUT = Path("features.json")
    WINDOW_SIZE = 12          # 12 × 5min = 1h rolling window nên là 1 tiếng sẽ là gom 12 vào window
    QUEUE_MAX_SIZE = 1000     # set threshold là 1000 đề phòng trường hợp cháy RAM
    PRODUCER_DELAY = 0.0      # set delay là 0 để mô phỏng real time


class Producer:
    def __init__(self, q: queue.Queue) -> None:
        self.q = q
        self.n_emitted = 0

    def _ensure_data(self) -> None:
        if not Config.CSV_PATH.exists():
            logger.info("Downloading dataset...")
            urllib.request.urlretrieve(Config.CSV_URL, Config.CSV_PATH)

    def run(self) -> None:
        self._ensure_data()
        df = pd.read_csv(Config.CSV_PATH, parse_dates=["timestamp"])
        logger.info("Producer: loaded %d rows", len(df))

        try:
            for _, row in df.iterrows():
                # Đọc csv, chuyển đổi về chuẩn json rồi nhét vào queue
                self.q.put({"timestamp": str(row["timestamp"]), "value": float(row["value"])})
                self.n_emitted += 1
                if Config.PRODUCER_DELAY:
                    time.sleep(Config.PRODUCER_DELAY)
                # log mỗi 5000 row thay vì mỗi row để tránh spam
                if self.n_emitted % 5_000 == 0:
                    logger.info("Producer: %d / %d", self.n_emitted, len(df))
        except Exception as e:
            logger.error("Producer error: %s", e)
        finally:
            self.q.put(None)  # Đặt 1 cái none và queue, mục đích thông báo rằng đã hết logs
            logger.info("Producer: done (%d events)", self.n_emitted)


class Consumer:
    def __init__(self, q: queue.Queue) -> None:
        self.q = q
        self.results: List[Dict[str, Any]] = []
        self._window: deque = deque(maxlen=Config.WINDOW_SIZE)
        self._prev_value: Optional[float] = None

    def _extract_features(self, event: Dict[str, Any]) -> Dict[str, Any]:
        value = event["value"]
        self._window.append(value)

        rate_of_change = value - self._prev_value if self._prev_value is not None else float("nan")
        self._prev_value = value

        features = {
            "timestamp":       event["timestamp"],
            "value":           value,
            "rate_of_change":  rate_of_change,
            "rolling_mean_1h": float("nan"),
            "rolling_std_1h":  float("nan"),
            "rolling_min_1h":  float("nan"),
            "rolling_max_1h":  float("nan"),
            "zscore":          float("nan"),
            "is_anomaly":      0,
        }

        # chỉ cho phép tính toán khi đã gom đủ window
        if len(self._window) == Config.WINDOW_SIZE:
            win = np.array(self._window)
            
            features["rolling_mean_1h"] = mean = float(np.mean(win))
            features["rolling_std_1h"]  = std  = float(np.std(win))
            features["rolling_min_1h"]  = float(np.min(win))
            features["rolling_max_1h"]  = float(np.max(win))

            # kiểm tra anomaly bằng z-score
            if std > 0:
                zscore = (value - mean) / std
                features["zscore"] = zscore
                features["is_anomaly"] = int(abs(zscore) > 3.0)

        return features

    def run(self) -> None:
        logger.info("Consumer: started")
        count = 0

        while True:
            try:
                event = self.q.get(timeout=30)
            except queue.Empty:
                logger.warning("Consumer: timed out waiting for events")
                break # nếu ko có data nữa thì out

            if event is None: # nhận 1 cái none từ hàm Producer
                self.q.task_done()
                break

            self.results.append(self._extract_features(event))
            count += 1
            self.q.task_done()

            if count % 5_000 == 0:
                logger.info("Consumer: processed %d", count)

        logger.info("Consumer: done (%d events)", count)

    def save(self) -> None:
        if not self.results:
            logger.warning("Nothing to save")
            return

        df = pd.DataFrame(self.results)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Lưu toàn bộ ra Parquet
        df.to_parquet(Config.PARQUET_OUTPUT, index=False)
        logger.info("Saved Parquet → %s", Config.PARQUET_OUTPUT)

        # Lưu thẳng toàn bộ ra JSON, không cần cắt sample nữa
        df.to_json(Config.JSON_OUTPUT, orient="records", indent=2, date_format="iso")
        logger.info("Saved JSON → %s", Config.JSON_OUTPUT)

        n_anomalies = int(df["is_anomaly"].sum())
        logger.info(
            "Summary: %d rows | %d anomalies (%.2f%%) | value range [%.2f, %.2f]",
            len(df), n_anomalies, 100 * n_anomalies / len(df),
            df["value"].min(), df["value"].max(),
        )


class StreamingPipeline:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue(maxsize=Config.QUEUE_MAX_SIZE)
        self._producer = Producer(self._q)
        self._consumer = Consumer(self._q)

    def run(self) -> None:
        t0 = time.perf_counter()

        producer_thread = threading.Thread(target=self._producer.run, name="Producer", daemon=True)
        consumer_thread = threading.Thread(target=self._consumer.run, name="Consumer", daemon=True)

        producer_thread.start()
        consumer_thread.start()
        producer_thread.join()
        consumer_thread.join()

        self._consumer.save()

        elapsed = time.perf_counter() - t0
        logger.info("Pipeline finished in %.2f s (%.0f events/s)", elapsed, len(self._consumer.results) / elapsed)


if __name__ == "__main__":
    pipeline = StreamingPipeline()
    pipeline.run()
