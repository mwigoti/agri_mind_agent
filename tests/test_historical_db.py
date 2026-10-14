import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "historical_records.db")

def test_database():
    assert os.path.exists(DB_PATH), f"Database not found at {DB_PATH}"
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Test tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print(f"Found tables in SQLite: {tables}")
    assert "agro_ecological_baselines" in tables
    assert "farmer_seasonal_history" in tables

    # 2. Test querying Nakuru baseline
    cur.execute("SELECT county, historical_mean_ndvi, benchmark_yield_t_ha FROM agro_ecological_baselines WHERE county = 'Nakuru';")
    row = cur.fetchone()
    print(f"Nakuru baseline query result: {row}")
    assert row is not None
    assert row[0] == "Nakuru"
    assert row[1] == 0.68
    assert row[2] == 4.20

    # 3. Test querying Plot 1 farmer seasonal average
    cur.execute("SELECT AVG(actual_yield_t_ha) FROM farmer_seasonal_history WHERE plot_id = 1;")
    avg_yield = cur.fetchone()[0]
    print(f"Plot 1 3-season average yield: {avg_yield:.2f} t/ha")
    assert round(avg_yield, 2) == 4.10

    conn.close()
    print("ALL SQLite historical archive verification tests PASSED!")

if __name__ == "__main__":
    test_database()
