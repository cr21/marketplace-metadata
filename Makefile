.PHONY: lint typecheck test demo bq-init bq-init-lineage demo-m00 demo-m01 demo-m02 demo-m03

lint:
	$(MAKE) -C infra lint

typecheck:
	$(MAKE) -C infra typecheck

test:
	$(MAKE) -C infra test

demo:
	$(MAKE) -C infra demo

bq-init:
	$(MAKE) -C infra bq-init

bq-init-lineage:
	$(MAKE) -C infra bq-init-lineage

demo-m00:
	$(MAKE) -C infra demo-m00

demo-m01:
	$(MAKE) -C infra demo-m01

demo-m02:
	$(MAKE) -C infra demo-m02

demo-m03:
	$(MAKE) -C infra demo-m03
