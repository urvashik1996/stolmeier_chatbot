from thefuzz import fuzz, process

# Test fuzzy matching
print(fuzz.ratio("car accident", "car accidents"))
print(process.extractOne("car accident", ["car accidents", "personal injury", "family law"], scorer=fuzz.token_sort_ratio))