from AlgorithmImports import *
from Selection.FundamentalUniverseSelectionModel import FundamentalUniverseSelectionModel

class AlphaLegionAlgorithm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(1997, 1, 1)
        self.SetCash(10000)
        self.SetBenchmark("SPY")
        
        self.SetSecurityInitializer(lambda s: s.SetFeeModel(ConstantFeeModel(1)))
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetUniverseSelection(RobsFundamentalUniverseSelectionModel())
        self.SetAlpha(ConstantAlphaModel(InsightType.Price, InsightDirection.Up, TimeSpan.FromDays(1)))
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetPortfolioConstruction(PeriodBasedSectorLimitedPortfolioConstructionModel())
        self.SetExecution(ImmediateExecutionModel())
        # Variable to hold the last calculated benchmark value
        self.lastBenchmarkValue = None
        # Our inital benchmark value scaled to match our portfolio
        self.benchmarkPerformance = self.Portfolio.TotalPortfolioValue
        # Initialize the plotting period
        self.plottingPeriod = -1
        
    def OnData(self, data):
        # Return if there are no investments
        if not self.Portfolio.Invested:
            return
        # Plot once every month because I'm too poor to buy a subscription and it limits at 4000 points/chart
        period = self.Time.month
        if period == self.plottingPeriod:
            return
        self.plottingPeriod = period
        
        # store the current benchmark close price
        benchmark = self.Benchmark.Evaluate(self.Time)
        # Calculate the performance of our benchmark and update our benchmark value for plotting
        if self.lastBenchmarkValue is not None:
           self.benchmarkPerformance = self.benchmarkPerformance * (benchmark/self.lastBenchmarkValue)
        # store today's benchmark price for use tomorrow
        self.lastBenchmarkValue = benchmark
        # make our plots
        self.Plot("Strategy vs Benchmark", "Portfolio Value", self.Portfolio.TotalPortfolioValue)
        self.Plot("Strategy vs Benchmark", "Benchmark", self.benchmarkPerformance)
        

class RobsFundamentalUniverseSelectionModel(FundamentalUniverseSelectionModel):
    
    def __init__(self, filterFineData = True, universeSettings = None):
        '''Initializes a new default instance of the RobsFundamentalUniverseSelectionModel'''
        super().__init__(filterFineData, universeSettings)
        self.lastPeriod = -1
        
    def SelectCoarse(self, algorithm, coarse):
        '''Performs coarse selection for constituents.
        The stocks must have fundamental data and a price of 1'''
        period = algorithm.Time.year
        if period == self.lastPeriod:
            return Universe.Unchanged
        self.lastPeriod = period
        
        # select those stocks which have a stock price at least one
        return list(map(lambda s: s.Symbol, [x for x in coarse if x.HasFundamentalData]))
        
    def SelectFine(self, algorithm, fine):
        '''Performs a selection based on several fundamental criteria.'''
        filteredFine = [x for x in fine if (x.CompanyReference.CountryId == "USA" 
                                            or x.CompanyReference.CountryId == "GBR"
                                            or x.CompanyReference.CountryId == "DEU"
                                            or x.CompanyReference.CountryId == "FRA")
                                        and x.MarketCap > 2000000000
                                        and x.ValuationRatios.PERatio <= 25
                                        and x.ValuationRatios.PERatio > 0
                                        and x.ValuationRatios.EVToEBITDA <= 25
                                        and x.ValuationRatios.EVToEBITDA > 0
                                        and x.OperationRatios.QuickRatio.OneYear >= 1
                                        and x.FinancialStatements.BalanceSheet.NetDebt.TwelveMonths < 3.5 * x.FinancialStatements.IncomeStatement.EBITDA.TwelveMonths
                                        and x.OperationRatios.RevenueGrowth.ThreeYears > 0.07
                                        and x.OperationRatios.NetIncomeGrowth.ThreeYears > 0]
        
        sortedFine = sorted(list(filteredFine), key=lambda x: x.ValuationRatios.EVToEBITDA)
        
        sectorCodeToCount = {}
        sectorToSymbol = {}
        finalSelection = []
        for co in sortedFine:
            if len(finalSelection) == 20:
                break
            
            sectorCode = co.AssetClassification.MorningstarSectorCode
            # skip if there are too many companies in a sector has been added
            count = sectorCodeToCount.get(sectorCode, 0)
            if count > 6:
                continue
            newCount = count + 1
            sectorCodeToCount[sectorCode] = newCount
            # add the symbol to the final list
            finalSelection.append(co.Symbol)
            # collect some debug information
            symbolList = sectorToSymbol.get(sectorCode, [])
            symbolList.append(co.Symbol)
            sectorToSymbol[sectorCode] = symbolList
            
        algorithm.Debug("Time: " + str(algorithm.Time))
        algorithm.Debug("Companies by sector")
        for se in sectorToSymbol.keys():
            algorithm.Debug(str(se) + ": " + ','.join(map(lambda s: s.Value, sectorToSymbol[se])))
        
        return finalSelection
        
class PeriodBasedSectorLimitedPortfolioConstructionModel(EqualWeightingPortfolioConstructionModel):
    
    def __init__(self):
        '''Initializes a new instance of the PeriodBasedSectorLimitedPortfolioConstructionModel.
        This model allows a rebalance once a year. Portfolio holdings will be equally weighted.'''
        super().__init__()
        
        self.lastPeriodOnChanged = -1
        self.lastPeriodCreateTargets = -1
        self.lastTargets = []
        
    def OnSecuritiesChanged(self, algorithm, changes):
        if self.lastPeriodOnChanged != algorithm.Time.year:
            self.lastPeriodOnChanged = algorithm.Time.year
            super().OnSecuritiesChanged(algorithm, changes)
            
    def CreateTargets(self, algorithm, insights):
        if self.lastTargets is None or self.lastPeriodCreateTargets != algorithm.Time.year:
            self.lastPeriodCreateTargets = algorithm.Time.year
            self.lastTargets = super().CreateTargets(algorithm, insights)
        return self.lastTargets
