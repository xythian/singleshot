
#
# Simple, dumb Makefile to make a distribution tarball
#

VERSION=1.0.1

clean:
	rm -rf build

dist: dist.tar.gz dist.zip

distdirectory: clean	
	mkdir build
	rm -rf build/singleshot-$(VERSION)
	mkdir build/singleshot-$(VERSION)
	cp .htaccess build/singleshot-$(VERSION)/root-htaccess
	cp readme build/singleshot-$(VERSION)/README
	cp LICENSE build/singleshot-$(VERSION)/LICENSE
	cp ChangeLog.txt build/singleshot-$(VERSION)/ChangeLog.txt
	mkdir build/singleshot-$(VERSION)/singleshot
	find . -regex "./singleshot/[^/]*.py" \
	       -o -path "./singleshot/.htaccess" \
	       -o -path "./singleshot/ss.css" \
	       -o -path "./singleshot/*.gif" \
	       -o \(     -name "album*.tmpl" \
	            -o  -name css.tmpl \
		    -o  -name nextprev.tmpl \
   		    -o  -name header.tmpl \
		    -o  -name slide.tmpl \
		    -o  -name tree.tmpl \
   		    -o  -name view.tmpl \
		    -o  -name bracket.tmpl \
		    -o  -name bigtee.tmpl \) | ( \
            cd build/singleshot-$(VERSION); \
	    while read COPYFILE; do \
		mkdir -p `dirname $$COPYFILE`; \
		cp ../../$$COPYFILE $$COPYFILE; \
	    done) 

dist.tar.gz: distdirectory
	(cd build; tar cvzf singleshot-$(VERSION).tar.gz  singleshot-$(VERSION))

test: clean dist.tar.gz
	@cp -r tests build
	@cp build/singleshot-$(VERSION).tar.gz build/tests/
	make VERSION=$(VERSION) -C build/tests test
	

dist.zip: distdirectory
	(cd build; zip -r singleshot-$(VERSION).zip singleshot-$(VERSION))
	  
