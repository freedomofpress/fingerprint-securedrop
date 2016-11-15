package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"math/rand"
	"os"
	"path"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	// SiteNum is the number of sites.
	SiteNum int = 100
	// InstNum is the total number of instances for each class.
	InstNum int = 90
	// TrainNum is the number of instances for training.
	TrainNum int = 60
	// TestNum is the number of instances of testing.
	TestNum int = 30
	// OpenTestNum is the number of instances for open-world testing.
	OpenTestNum int = 9000
	// The number of training rounds
	Rounds int = 10

	// FolderWeight is the folder for weight learning.
	FolderWeight = "batch/"
	// FolderOpen is the folder for the open-world.
	FolderOpen = "batch/"
	// FolderTrain is the folder for training.
	FolderTrain = "batch/"
	// FolderTest is the folder for testing.
	FolderTest = "batch/"
	// FeatureSuffix is the suffix of files containing features
	FeatureSuffix = "s"

	// FeatNum is the number of extracted features to consider.
	FeatNum int = 1225
	// NeighbourNum is the number of neighbours in kNN.
	NeighbourNum int = 2
	// RecoPointsNum is the number of neighbours for distance learning.
	RecoPointsNum int = 5
)

func dist(f1, f2, weight []float64, presentFeats []int) (d float64) {
	for _, i := range presentFeats {
		if f2[i] != -1 {
			d += weight[i] * math.Abs(f1[i]-f2[i])
		}
	}
	return
}

func getMin(f []float64) (val float64, index int) {
	index = 0
	val = f[0]
	for i := 0; i < len(f); i++ {
		if f[i] < val {
			val = f[i]
			index = i
		}
	}
	return
}

func getMax(f []float64) (val float64, index int) {
	index = 0
	val = f[0]
	for i := 0; i < len(f); i++ {
		if f[i] > val {
			val = f[i]
			index = i
		}
	}
	return
}

func initWeight(weight []float64) {
	// as in alg_init_weight
	for i := 0; i < FeatNum; i++ {
		weight[i] = rand.Float64() + 0.5
	}
}

func determineWeights(feat [][]float64, weight []float64, start, end int) {
	presentFeats := make([]int, FeatNum)
	distList := make([]float64, SiteNum*TrainNum)
	var wg sync.WaitGroup
	recoGoodList := make([]int, RecoPointsNum)
	recoBadList := make([]int, RecoPointsNum)
	log.Printf("starting to learn distance...")
	for i := start; i < end; i++ {
		for r := 0; r < Rounds; r++ {
			fmt.Printf("\r\tdistance... %d (%d-%d), round... %d (%d)", i,
				start, end, r, Rounds)

			curSite := int(i / TrainNum)
			var pointBadness, maxGoodDist float64

			// determine what features are present for the instance we're training on
			numPresent := 0
			for j := 0; j < FeatNum; j++ {
				if feat[i][j] != -1 {
					presentFeats[numPresent] = j
					numPresent++
				}
			}

			// calculate the distance to every other instance
			for j := 0; j < SiteNum*TrainNum; j++ {
				wg.Add(1)
				go func(distList, weight []float64, presentFeats []int, i, j, numPresent int) {
					defer wg.Done()
					distList[j] = dist(feat[i], feat[j], weight, presentFeats[:numPresent])
				}(distList, weight, presentFeats, i, j, numPresent)
			}

			// wait for all distances to finishes computing (goroutines)
			wg.Wait()
			// don't consider the distance to itself
			max, _ := getMax(distList)
			distList[i] = max

			// recoGoodList: find the RecoPoinsNum number of closest instances for _the same_ site
			for j := 0; j < RecoPointsNum; j++ {
				_, minIndex := getMin(distList[curSite*TrainNum : (curSite+1)*TrainNum])
				minIndex += curSite * TrainNum // we have to add the off-set in the index above

				if distList[minIndex] > maxGoodDist {
					maxGoodDist = distList[minIndex]
				}
				distList[minIndex] = max // make sure we don't select the same instance again
				recoGoodList[j] = minIndex
			}

			// make sure we don't consider any instances for the current site in the future
			for j := 0; j < TrainNum; j++ {
				distList[curSite*TrainNum+j] = max
			}

			// recoBadList: find the RecoPoinsNum number of closest instances for _other_ sites
			for j := 0; j < RecoPointsNum; j++ {
				_, minIndex := getMin(distList)
				if distList[minIndex] <= maxGoodDist {
					pointBadness++
				}
				distList[minIndex] = max // make sure we don't select the same instance again
				recoBadList[j] = minIndex
			}

			pointBadness /= float64(RecoPointsNum)
			pointBadness += 0.2

			featDist := make([]float64, FeatNum)
			badList := make([]int, FeatNum)
			var minBadList int

			for j := 0; j < FeatNum; j++ {
				if weight[j] == 0 {
					badList[j] = 0
					panic("does this ever happen?")
					//continue
				}

				var maxGood float64
				var countBad int
				// find maxGood
				for k := 0; k < RecoPointsNum; k++ {
					n := math.Abs(feat[i][j] - feat[recoGoodList[k]][j])
					if feat[i][j] == -1 || feat[recoGoodList[k]][j] == -1 {
						n = 0
					}
					if n >= maxGood {
						maxGood = n
					}
				}

				for k := 0; k < RecoPointsNum; k++ {
					n := math.Abs(feat[i][j] - feat[recoBadList[k]][j])
					if feat[i][j] == -1 || feat[recoBadList[k]][j] == -1 {
						n = 0
					}
					featDist[j] += n
					if n <= maxGood {
						countBad++
					}
				}
				badList[j] = countBad
				if countBad < minBadList {
					minBadList = countBad
				}
			}

			var countBadList int
			for j := 0; j < FeatNum; j++ {
				if badList[j] != minBadList {
					countBadList++
				}
			}

			// update weights
			change := make([]float64, countBadList)
			tmp := 0
			var c1 float64
			for j := 0; j < FeatNum; j++ {
				if badList[j] != minBadList {
					change[tmp] = weight[j] * 0.01 * float64(badList[j]) / float64(RecoPointsNum) * pointBadness
					c1 += change[tmp] * featDist[j]
					weight[j] -= change[tmp]
					tmp++
				}
			}

			var totalfd float64
			for j := 0; j < FeatNum; j++ {
				if badList[j] == minBadList && weight[j] > 0 {
					totalfd += featDist[j]
				}
			}

			for j := 0; j < FeatNum; j++ {
				if badList[j] == minBadList && weight[j] > 0 {
					weight[j] += c1 / totalfd
				}
			}
		}

		for i := 0; i < FeatNum; i++ {
			if weight[i] > 0 {
				weight[i] *= 0.9 + rand.Float64()*0.2
			}
		}

	}
	fmt.Print("\n")
	log.Printf("finished")
}

func accuracy(trainclosedfeat, testclosedfeat, openfeat [][]float64, weight []float64) (tp, tn float64) {
	//trainclosedfeat is the "background" knn closed points.
	//testclosedfeat is the possibly modified knn closed points that we want to test accuracy on
	//testclosedfeat = trainclosedfeat is normal
	//openfeat is the knn open points. they are also tested.

	// new data to datastructures to include openfeatures
	trainfeat := make([][]float64, SiteNum*TestNum+OpenTestNum)
	testfeat := make([][]float64, SiteNum*TestNum+OpenTestNum)
	for i := 0; i < SiteNum*TestNum; i++ {
		trainfeat[i] = trainclosedfeat[i]
		testfeat[i] = testclosedfeat[i]
	}
	for i := 0; i < OpenTestNum; i++ {
		trainfeat[i+SiteNum*TestNum] = openfeat[i]
		testfeat[i+SiteNum*TestNum] = openfeat[i]
	}

	// setup file logging
	f, err := os.OpenFile("flearner."+strconv.Itoa(int(time.Now().Unix()))+".log",
		os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		log.Fatalf("error opening file: %v", err)
	}
	defer f.Close()
	flog := log.New(f, "", log.Ldate|log.Ltime)

	presentFeats := make([]int, FeatNum)
	distList := make([]float64, SiteNum*TestNum+OpenTestNum)
	var wg sync.WaitGroup
	classList := make([]int, SiteNum+1)

	log.Println("started computing accuracy...")
	for is := 0; is < SiteNum*TestNum+OpenTestNum; is++ {
		fmt.Printf("\r\taccuracy... %d (%d-%d)", is, 0, SiteNum*TestNum+OpenTestNum)

		// determine what features are present for the instance we're classifying
		numPresent := 0
		for j := 0; j < FeatNum; j++ {
			if testfeat[is][j] != -1 {
				presentFeats[numPresent] = j
				numPresent++
			}
		}

		// reset classList and calculate all distances
		for i := 0; i < SiteNum+1; i++ {
			classList[i] = 0
		}
		for at := 0; at < SiteNum*TestNum+OpenTestNum; at++ {
			wg.Add(1)
			go func(distList, weight []float64, presentFeats []int, is, at, numPresent int) {
				defer wg.Done()
				distList[at] = dist(testfeat[is], trainfeat[at], weight, presentFeats[:numPresent])
			}(distList, weight, presentFeats, is, at, numPresent)
		}

		// wait for all distances to finishes computing (goroutines)
		wg.Wait()
		max, _ := getMax(distList)
		distList[is] = max // don't consider the point representing this instance

		var maxClass int
		flog.Print("Guessed classes: ")
		for i := 0; i < NeighbourNum; i++ {
			_, index := getMin(distList)

			classIndex := SiteNum
			if index < SiteNum*TestNum {
				classIndex = index / TestNum
			}
			classList[classIndex]++

			if classList[classIndex] > maxClass {
				maxClass = classList[classIndex]
			}
			distList[index] = max
			flog.Printf("\t %d", classIndex)
		}

		trueClass := is / TestNum
		if trueClass > SiteNum {
			// we use the last class to represent all open-world sites
			trueClass = SiteNum
		}
		flog.Printf("true class %d\n", trueClass)

		var countClass int
		var consensus, correct bool = false, false
		for i := 0; i < SiteNum+1; i++ {
			if classList[i] == NeighbourNum {
				consensus = true
				break
			}
		}

		if !consensus {
			for i := 0; i < SiteNum; i++ {
				classList[i] = 0
			}
			classList[SiteNum] = 1
			maxClass = 1
		}

		for i := 0; i < SiteNum+1; i++ {
			if classList[i] == maxClass {
				countClass++
				if i == trueClass {
					correct = true
				}
			}
		}

		var thisacc float64
		if correct {
			thisacc = float64(1.0 / countClass)
		}
		if trueClass == SiteNum {
			tn += thisacc
		} else {
			tp += thisacc
		}
	}

	tp /= float64(SiteNum * TestNum)
	tn /= float64(OpenTestNum)
	if OpenTestNum == 0 {
		tn = 1
	}

	fmt.Print("\n")
	log.Println("finished")
	return
}

func readFile(folder, name string, sites, start int, end int, openWorld bool) (feat [][]float64) {
	instances := end - start
	// create the feature data structure to store what we read
	feat = make([][]float64, sites*instances)
	for i := 0; i < len(feat); i++ {
		feat[i] = make([]float64, FeatNum)
	}

	// iterate over each site-instance
	for curSite := 0; curSite < sites; curSite++ {
		failCount := 0
		curInstAbs := 0
		for curInst := start; curInst < end; curInst++ {
			// read the next file with features, continuing to the next instance if one is missing
			// this was the approach in the original code, so presumably we need it to parse their data
			var features string
			for {
				filename := path.Join(folder,
					strconv.Itoa(curSite)+"-"+strconv.Itoa(curInst+failCount)+FeatureSuffix)
				if openWorld {
					// only one instance in the open world
					filename = path.Join(folder, strconv.Itoa(curSite)+FeatureSuffix)
				}
				d, err := ioutil.ReadFile(filename)
				if err != nil {
					if failCount > 1000 {
						log.Fatalf("failed to find instance files to read (at least 1000 instances missing) for filename %s", filename)
					}
					failCount++
					continue
				}
				features = string(d)
				break
			}

			// extract features
			fCount := 0
			for _, f := range strings.Split(features, " ") {
				curIndex := curSite*instances + curInstAbs
				if f == "'X'" {
					feat[curIndex][fCount] = -1
				} else if f != "" {
					feat[curIndex][fCount] = parseFeatureString(f)
				}
				fCount++
			}
			curInstAbs++
		}
	}

	log.Printf("loaded instances: %s", name)
	return
}

func parseFeatureString(c string) float64 {
	val, err := strconv.ParseFloat(c, 64)
	if err != nil {
		panic(err)
	}
	return val
}

func main() {
	// load features from collected traces for (in this order):
	// - weight learning (always closed world)
	// - training and testing (closed world)
	// - open world
	feat := readFile(FolderWeight, "main", SiteNum, TestNum, InstNum, false)
	trainclosedfeat := readFile(FolderTrain, "training", SiteNum, 0, TestNum, false)
	testclosedfeat := readFile(FolderTest, "testing", SiteNum, 0, TestNum, false)
	openfeat := readFile(FolderOpen, "open", OpenTestNum, 0, 1, true)

	// determine weights
	weight := make([]float64, FeatNum)
	initWeight(weight)
	determineWeights(feat, weight, 0, SiteNum*TrainNum)

	// calculate the accuracy in terms of true positives and true negatives
	tp, tn := accuracy(trainclosedfeat, testclosedfeat, openfeat, weight)
	log.Printf("Accuracy: %f %f", tp, tn)

	f, err := os.OpenFile("weights."+strconv.Itoa(int(time.Now().Unix())),
		os.O_RDWR|os.O_CREATE|os.O_APPEND, 0666)
	if err != nil {
		log.Fatalf("error opening file: %v", err)
	}
	defer f.Close()
	for i := 0; i < FeatNum; i++ {
		fmt.Fprintf(f, "%f ", weight[i]*1000)
	}
}
