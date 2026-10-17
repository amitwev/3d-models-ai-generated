CXX ?= g++
CXXFLAGS = -std=c++17 -Wall -Wextra -Werror -I../Mobula7Link/src

.PHONY: test
test:
	@mkdir -p build
	$(CXX) $(CXXFLAGS) *.cpp -o build/tests
	./build/tests
