"""Normalize historical plural wording without changing custom questions."""
LABELS={'Veröffentlichung auf den Homepages':'Veröffentlichung auf der Homepage'}
def question_label(value):return LABELS.get(value,value)
