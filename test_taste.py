from scripts.segmentation import CustomerSegmentation
seg = CustomerSegmentation()
results = seg.cluster_by_taste_preferences()
print('Clustered', len(results), 'customers by taste preferences')
for r in results[:5]:
    print(r['customer_id'], ':', r['taste'])