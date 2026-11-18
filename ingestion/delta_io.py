"""Leitura de tabelas Delta pelos arquivos que o log aponta, com pyarrow puro.

`DeltaTable.to_pyarrow_table()` aborta o processo ao sair ("terminate called
without an active exception", testado no deltalake 0.22, 0.25 e 1.1 em
aarch64): o sistema de arquivos Rust que ele registra no pyarrow é destruído
fora de ordem. Ler a lista de arquivos da versão atual (`file_uris`) com o
leitor Parquet do pyarrow dá o mesmo conteúdo e não tem o problema.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
from deltalake import DeltaTable


def read_delta(path: str | Path, columns: list[str] | None = None, filter=None) -> pa.Table:
    table = DeltaTable(str(path))
    files = table.file_uris()
    if not files:
        return pa.table({})
    dataset = ds.dataset(
        files,
        format="parquet",
        partitioning=ds.HivePartitioning.discover(infer_dictionary=False),
        partition_base_dir=str(Path(path).resolve()),
    )
    return dataset.to_table(columns=columns, filter=filter)
