#/usr/bin/env python

# based on https://github.com/KDahlgren/pyLDFI/blob/master/src/wrappers/c4/C4Wrapper.py

#############
#  IMPORTS  #
#############
# standard python packages
import logging, inspect, os, string, sys, time
from ctypes import *
from types  import *

# ------------------------------------------------------ #
# import sibling packages HERE!!!
if not os.path.abspath( __file__ + "/../.." ) in sys.path :
  sys.path.append( os.path.abspath( __file__ + "/../.." ) )

# ------------------------------------------------------ #


class C4Wrapper( object ) :

  ##########
  #  INIT  #
  ##########
  def __init__( self ) :

    c4_lib_loc                     = os.path.abspath( __file__ + '/../../../lib/c4/build/src/libc4/libc4.dylib' )
    self.lib                       = cdll.LoadLibrary( c4_lib_loc )
    self.lib.c4_make.restype       = POINTER(c_char)
    self.lib.c4_dump_table.restype = c_char_p   # c4_dump_table returns a char*


  #########################
  #  GET INPUT PROG FILE  #
  #########################
  def getInputProg_file( self, filename ) :
    if DEBUG :
      logging.debug( "Importing program from " + filename )

    try :
      program = []
      fo = open( filename, "r" )
      for line in fo :
        line = line.rstrip()
        program.append( line )
      fo.close()

      return "".join( program )

    except IOError :
      logging.error( "Could not open file " + filename )
      return None


  ########################################################################################
  #  GET INPUT PROG ONE GROUP FOR EVERYTHING BESIDES CLOCKS AND GROUP CLOCKS BY SNDTIME  #
  ########################################################################################
  # this is what molly does.
  def getInputProg_one_group_for_everything_besides_clocks_and_group_clocks_by_sndTime( self, program ) :

    nonClock             = []
    clockStatementGroups = [] # list of strings grouping clock statements by SndTime
    currClockList        = ""
    currTime             = 1

    # ---------------------------------------------------------------------- #
    # only works if clock facts are sorted by increasing SndTime when 
    # appearing in the input c4 line list.
    # also only works if simulations start at time 1.
    for i in range(0 ,len(program)) :

      statement = program[i]
      nextStatement = None
      lastClock     = False

      parsedStatement = statement.split( "(" )

      # ---------------------------------------------------------------------- #
      # CASE : hit a clock fact
      if parsedStatement[0] == "clock" :

        # ---------------------------------------------------------------------- #
        # check if the next statement in the program also declares a clock fact
        try :
          nextStatement    = program[ i+1 ]
          parsedStatement1 = nextStatement.split( "(" )
          assert( parsedStatement1[0] == "clock" )
        except :
          lastClock = True

        parsedClockArgs = parsedStatement[1].split( "," ) # split clock fact arguments into a list

        # ---------------------------------------------------------------------- #
        # check if SndTime is in the current group
        if not lastClock and int( parsedClockArgs[2] ) == currTime :
          currClockList += statement

        # ---------------------------------------------------------------------- #
        # hit a clock fact in the next time group
        elif not lastClock and int( parsedClockArgs[2] ) > currTime :
          clockStatementGroups.append( currClockList ) # save the old clock group
          currClockList  = ""                          # reset the clock group
          currClockList += statement                   # reset the clock group
          currTime       = int( parsedClockArgs[2] )   # reset the curr time

        # ---------------------------------------------------------------------- #
        # hit a clock fact in the next time group and last clock true
        elif lastClock and int( parsedClockArgs[2] ) > currTime :
          clockStatementGroups.append( currClockList ) # save the old clock group
          currClockList  = ""                          # reset the clock group
          currClockList += statement                   # reset the clock group
          currTime       = int( parsedClockArgs[2] )   # reset the curr time
          clockStatementGroups.append( currClockList ) # save the old clock group

        # ---------------------------------------------------------------------- #
        # hit a clock fact in the last time group
        elif lastClock :
          currClockList += statement
          clockStatementGroups.append( currClockList ) # save the old clock group

      # ---------------------------------------------------------------------- #
      # CASE : hit a non clock fact
      else :
        nonClock.append( statement )

    finalProg    = []
    nonClock_str = "".join( nonClock )

    finalProg.append( nonClock_str )          # add all non-clock clock statements
    finalProg.extend( clockStatementGroups )  # add clock statements

    return finalProg


  ######################################
  #  GET INPUT PROG GROUP CLOCKS ONLY  #
  ######################################
  def getInputProg_group_clocks_only( self, program ) :

    finalProg            = []
    clockStatementGroups = [] # list of strings grouping clock statements by SndTime
    currClockList        = ""
    currTime             = 1

    # only works if clock facts are sorted by increasing SndTime when 
    # appearing in the input c4 line list.
    # also only works if simulations start at time 1.
    for i in range(0 ,len(program)) :

      statement = program[i]
      nextStatement = None
      lastClock     = False

      parsedStatement = statement.split( "(" )

      # CASE : hit a clock fact
      if parsedStatement[0] == "clock" :

        # check if the next statement in the program also declares a clock fact
        try :
          nextStatement    = program[ i+1 ]
          parsedStatement1 = nextStatement.split( "(" )
          parsedClockArgs1 = parsedStatement1[1].split( "," ) # split clock fact arguments into a list
          assert( parsedStatement1[0] == "clock" )
        except :
          currClockList += statement
          lastClock = True

        parsedClockArgs = parsedStatement[1].split( "," ) # split clock fact arguments into a list

        # check if SndTime is in the current group
        if not lastClock and int( parsedClockArgs[2] ) == currTime :
          currClockList += statement

        # hit a clock fact in the next time group
        elif not lastClock and int( parsedClockArgs[2] ) > currTime :
          clockStatementGroups.append( currClockList ) # save the old clock group
          currClockList  = ""                          # reset the clock group
          currClockList += statement                   # reset the clock group
          currTime       = int( parsedClockArgs[2] )   # reset the curr time

        # hit a clock fact in the last time group
        elif lastClock :
          clockStatementGroups.append( currClockList ) # save the old clock group

      # CASE : hit a non clock fact
      else :
        finalProg.append( statement )

    finalProg.extend( clockStatementGroups )  # add clock statements

    return finalProg


  ####################################################
  #  GET INPUT PROG GROUP ALL AND CLOCKS BY SNDTIME  #
  ####################################################
  def getInputProg_group_all_and_clocks_by_sndtime( self, program ) :

    defineStatementsOnly = "" # string of defines statements only. no clocks or code.
    codeStatementsOnly   = "" # string of code statements only. no clock statements.
    clockStatementGroups = [] # list of strings grouping clock statements by SndTime
    currClockList        = ""
    currTime             = 1

    # only works if clock facts are sorted by increasing SndTime when 
    # appearing in the input c4 line list.
    # also only works if simulations start at time 1.
    for i in range(0 ,len(program)) :

      statement = program[i]
      nextStatement = None
      lastClock     = False

      parsedStatement = statement.split( "(" )

      # CASE : hit a define statement
      if parsedStatement[0] == "define" :
        defineStatementsOnly += statement

      # CASE : hit a clock fact
      elif parsedStatement[0] == "clock" :

        # check if the next statement in the program also declares a clock fact
        try :
          nextStatement    = program[ i+1 ]
          parsedStatement1 = nextStatement.split( "(" )
          parsedClockArgs1 = parsedStatement1[1].split( "," ) # split clock fact arguments into a list
          assert( parsedStatement1[0] == "clock" )
        except :
          currClockList += statement
          lastClock = True

        parsedClockArgs = parsedStatement[1].split( "," ) # split clock fact arguments into a list

        # check if SndTime is in the current group
        if not lastClock and int( parsedClockArgs[2] ) == currTime :
          currClockList += statement

        # hit a clock fact in the next time group
        elif not lastClock and int( parsedClockArgs[2] ) > currTime :
          clockStatementGroups.append( currClockList ) # save the old clock group
          currClockList  = ""                          # reset the clock group
          currClockList += statement                   # reset the clock group
          currTime       = int( parsedClockArgs[2] )   # reset the curr time

        # hit a clock fact in the last time group
        elif lastClock :
          clockStatementGroups.append( currClockList ) # save the old clock group

      # CASE : hit a non clock fact
      else :
        codeStatementsOnly += statement

    finalProg = []
    finalProg.append( defineStatementsOnly )  # add define statements
    finalProg.append( codeStatementsOnly   )  # add code statements
    finalProg.extend( clockStatementGroups )  # add clock statements

    return finalProg

  ##############
  #  RUN PURE  #
  ##############
  # fullprog is a string of concatenated overlog commands.
  def run_pure( self, allProgramData ) :

    allProgramLines = allProgramData[0] # := list of every code line in the generated C4 program.
    tableList       = allProgramData[1] # := list of all tables in generated C4 program.

    # get full program
    fullprog = "".join( allProgramLines )

    # ----------------------------------------- #

    # initialize c4 instance
    self.lib.c4_initialize()
    self.c4_obj = self.lib.c4_make( None, 0 )

    # ---------------------------------------- #
    # load program
    logging.debug( "... loading prog ..." )

    logging.debug( "SUBMITTING SUBPROG : " )
    logging.debug( fullprog )
    c_prog = bytes( fullprog )
    self.lib.c4_install_str( self.c4_obj, c_prog )

    # ---------------------------------------- #
    # dump program results to file
    logging.debug( "... dumping program ..." )

    results_array = self.saveC4Results_toArray( tableList )

    # ---------------------------------------- #
    # close c4 program
    logging.debug( "... closing C4 ..." )

    self.lib.c4_destroy( self.c4_obj )
    self.lib.c4_terminate( )

    return results_array


  ########################
  #  RUN PURE ITERATIVE  #
  ########################
  def run_pure_iterative( self, allProgramData ) :

    allProgramLines = allProgramData[0] # := list of every code line in the generated C4 program.
    tableList       = allProgramData[1] # := list of all tables in generated C4 program.

    # ----------------------------------------- #

    # initialize c4 instance
    self.lib.c4_initialize()
    self.c4_obj = self.lib.c4_make( None, 0 )

    # ---------------------------------------- #
    # load program
    logging.debug( "... loading prog ..." )

    logging.debug( "SUBMITTING SUBPROG : " )
    for line in allProgramLines :
      print "submitting line : " + line
      logging.debug( line )
      c_prog = bytes( line )
      self.lib.c4_install_str( self.c4_obj, c_prog )

    # ---------------------------------------- #
    # dump program results to file
    logging.debug( "... dumping program ..." )

    results_array = self.saveC4Results_toArray( tableList )

    # ---------------------------------------- #
    # close c4 program
    logging.debug( "... closing C4 ..." )

    self.lib.c4_destroy( self.c4_obj )
    self.lib.c4_terminate( )

    return results_array

  #########
  #  RUN  #
  #########
  # fullprog is a string of concatenated overlog commands.
  def run( self, allProgramData ) :

    allProgramLines = allProgramData[0] # := list of every code line in the generated C4 program.
    tableList       = allProgramData[1] # := list of all tables in generated C4 program.

    # get full program
    #fullprog = self.getInputProg_group_all_and_clocks_by_sndtime( allProgramLines ) # group statements, clocks by time.
    fullprog = self.getInputProg_one_group_for_everything_besides_clocks_and_group_clocks_by_sndTime( allProgramLines )
    #fullprog = self.getInputProg_group_clocks_only( allProgramLines )
    #fullprog = allProgramLines # no grouping, every code line installed separately.

    # ----------------------------------------- #
    # KD : bcsat debugging session 6/21/17
    logging.debug( "PRINTING RAW INPUT PROG" )
    for x in fullprog :
      logging.debug( x )

    logging.debug( "PRINTING LEGIBLE INPUT PROG" )
    for line in fullprog :
      line = line.split( ";" )
      for statement in line :
        statement = statement.rstrip()
        if not statement == "" :
          statement = statement + ";"
          logging.debug( statement )

    # ----------------------------------------- #

    # initialize c4 instance
    self.lib.c4_initialize()
    self.c4_obj = self.lib.c4_make( None, 0 )

    # ---------------------------------------- #
    # load program
    logging.debug( "... loading prog ..." )

    for subprog in fullprog :
      print ( "SUBMITTING SUBPROG : " )
      print ( subprog )
      c_prog = bytes( subprog )
      self.lib.c4_install_str( self.c4_obj, c_prog )

    # ---------------------------------------- #
    # dump program results to file
    logging.debug( "... dumping program ..." )

    results_array = self.saveC4Results_toArray( tableList )

    # ---------------------------------------- #
    # close c4 program
    logging.debug( "... closing C4 ..." )

    self.lib.c4_destroy( self.c4_obj )
    self.lib.c4_terminate( )

    return results_array


  ##############################
  #  SAVE C4 RESULTS TO ARRAY  #
  ##############################
  # save c4 results to array
  def saveC4Results_toArray( self, tableList ) :

    # save new contents
    results_array = []

    for table in tableList :

      # output to stdout
      logging.debug( "---------------------------" )
      logging.debug( table )
      logging.debug( self.lib.c4_dump_table( self.c4_obj, table ) )

      # save in array
      results_array.append( "---------------------------" )
      results_array.append( table )

      table_results_str   = self.lib.c4_dump_table( self.c4_obj, table )
      table_results_array = table_results_str.split( '\n' )
      results_array.extend( table_results_array[:-1] ) # don't add the last empty space

    return results_array


#########################
#  THREAD OF EXECUTION  #
#########################
if __name__ == '__main__' :

  logging.debug( "[ Executing C4 wrapper ]" )
  w = C4Wrapper( )

  # /////////////////////////////////// #
  rf = open( "./myTest.olg", "r" )
  prog1 = []
  for line in rf :
    line = line.rstrip()
    prog1.append( line )
  rf.close()

  rf = open( "./tableListStr_myTest.data", "r" )
  table_str1 = rf.readline()
  table_str1 = table_str1.rstrip()
  table_str1 = table_str1.split( "," )

  w.run( [ prog1, table_str1 ] )


#########
#  EOF  #
#########
