# Copyright (c) 2026 Zyphra, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import os
from nemo_text_processing.utils.logging import logger


def get_abs_path(rel_path: str) -> str:
    """Get absolute path relative to the pl package directory."""
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    if not os.path.exists(abs_path):
        logger.warning(f"{abs_path} does not exist")
    return abs_path


def load_labels(abs_path: str) -> list:
    """Loads TSV file as list of rows."""
    with open(abs_path, encoding="utf-8") as label_tsv:
        labels = list(csv.reader(label_tsv, delimiter="\t"))
    return labels
