import pandas as pd

# 1. Load the raw dataset
df = pd.read_csv('agrivision_realArea.csv')

# 2. Define the required columns based on your statistical equation
# Note: 'soc' and 'actual_yield_kgha' are not in this satellite dataset 
# and will need to be joined later using the [county, year] keys.
required_columns = [
    'county',          # Composite key
    'year',            # Composite key
    'ndre_veg_mean',   # NDRE_veg
    'ndvi_auc_full',   # NDVI_auc
    'ewa_grain_mm',    # EWA_grain
    'gdd_tassel',      # GDD_S3 (Using tassel phase as proxy; change to gdd_veg or gdd_grain if needed)
    'tsi_tassel'       # TSI_S3 (Using tassel phase as proxy; change to tsi_grain if needed)
]

# 3. Filter the dataframe to only keep the selected features
mlr_features_df = df[required_columns].copy()

# 4. (Optional) Rename columns to explicitly match your equation's terminology
rename_mapping = {
    'ndre_veg_mean': 'ndre_veg',
    'ndvi_auc_full': 'ndvi_auc',
    'ewa_grain_mm': 'ewa_grain',
    'gdd_tassel': 'gdd_s3',
    'tsi_tassel': 'tsi_s3'
}
mlr_features_df.rename(columns=rename_mapping, inplace=True)

# 5. Save the cleaned dataset to a new CSV file
output_filename = 'mlr_base_features.csv'
mlr_features_df.to_csv(output_filename, index=False)

print(f"Successfully extracted {len(mlr_features_df.columns)} columns.")
print("Saved to:", output_filename)
print("\nPreview of the new table:")
print(mlr_features_df.head())