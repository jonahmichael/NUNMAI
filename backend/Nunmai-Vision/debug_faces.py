from nunmai_vision.model.classifier import NunmaiVisionClassifier

clf = NunmaiVisionClassifier()
result = clf.classify_video('test_data/manipulated.mp4')

print(f"Aggregated: {result['prediction']} ({result['fake_probability']})")
print()
print("ALL per-face results:")
for i, r in enumerate(result['per_face_results']):
    marker = " <-- HIGH" if r['fake_probability'] > 0.3 else ""
    print(f"  Face {i+1}: fake_prob={r['fake_probability']:.6f}, label={r['label']}{marker}")