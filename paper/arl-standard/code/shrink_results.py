import sys, os, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
def shrink(src, dst):
    s = pq.read_schema(src)
    keep = [n for n in s.names if not n.startswith(("d_", "m_"))]
    keep += [n for n in ("m_sharpe_annualized", "m_deflated_sharpe", "m_total_return", "m_ic_mean", "m_ic_t_stat") if n in s.names]
    t = pq.read_table(src, columns=keep)
    for i, f in enumerate(t.schema):
        if f.name.startswith("m_") and pa.types.is_float64(f.type):
            t = t.set_column(i, f.name, pc.cast(t.column(i), pa.float32(), safe=False))
    pq.write_table(t, dst, compression="zstd", compression_level=19, row_group_size=len(t) or 1)
    sizes = {}
    m = pq.ParquetFile(dst).metadata
    for c in range(m.num_columns):
        x = m.row_group(0).column(c); sizes[x.path_in_schema] = x.total_compressed_size
    print(os.path.basename(dst), t.num_rows, t.num_columns, f"{os.path.getsize(dst)/1e6:.1f} MB; top", [(k, round(v/1e6,2)) for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:8]])
if __name__ == "__main__":
    shrink(sys.argv[1], sys.argv[2])
