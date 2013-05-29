'''
Iters over a list applying a list of @items on each 
obs: I could use map here, but map returns a list and eats up some memory
'''
def apply_pipeline(lst, *items):
	for applicable in lst:
		items  = applicable(*items)

	return items