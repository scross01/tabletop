tabletop-demo.gif: demo.tape
	vhs validate demo.tape
	vhs demo.tape

.PHONY: demo
demo: tabletop-demo.gif
