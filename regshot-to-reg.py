from __future__ import print_function
from collections import defaultdict
from datetime import datetime
import codecs, glob, os, re, sys

# Get file loaction
def getFileLoc():
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

# Get path and file name
def getFullPath(nameOnly = None):

    fileName = os.path.join(getFileLoc(), sys.argv[1])

    if nameOnly is None:
        return fileName

    return sys.argv[1].rsplit('.', 1)[0]

# Get files in directory
def getDirFiles(ext = None, stripExt = None):
    fileList = []

    # Set default search option
    if ext is None:
        ext = '*'

    # Compile names to list
    for fullName in glob.glob(getFileLoc() + '\\' + ext):
        name = fullName.rsplit('\\', 1)[1]

        # Set option to strip extension
        if stripExt is not None:
            name = name.rsplit('.', 1)[0]

        fileList.append(name)

    return fileList

# Handle debug
def doDebug(e, option):
    if option == '-d':
        raise
    elif option == '-df':
        # Set vars including date
        curDT = datetime.now()
        curDf = curDT.strftime('%Y-%m-%d')
        curTf = curDT.strftime('%I:%M:%S:%f %p')
        curTfCut = curTf[:11] + curTf[15:]
        fileName = 'rtr_debug_' + curDf + '.txt'

        debugFile = open(fileName, 'a')

        # Print errors to file
        print(curTfCut + '\n', file = debugFile)
        print(e, file = debugFile)
        print('\n----------\n', file = debugFile)
        print('Something went wrong. See \'' + fileName + '\'' + ' for more details.')

        debugFile.close()
    else:
        print(
            'Use \'-d\' at the second argument position to output errors here, '
            'otherwise use \'-df\' to output to a file'
        )

# Process data type: REG_DWORD
def procDword(value):
    return 'dword:' + value[2:].lower()

# Process data type: REG_EXPAND_SZ
def procExpand(value):
    # Remove quotes
    valueRmQuote = value[1:-1].lower()

    # Convert string to reg hex
    regHex = ',00,'.join(hex(ord(x))[2:] for x in valueRmQuote)

    return 'hex(2):' + regHex + ',00,00,00'

# Process data types: REG_BINARY, REG_QWORD, REG_MULTI_SZ
def procHex(dataType, value):
    prefix = ""

    if dataType == 'binary':
        prefix = 'hex'
    elif dataType == 'qword':
        prefix = 'hex(b)'
    elif dataType == 'multi':
        prefix = 'hex(7)'

    return prefix + ':' + value.lower().replace(' ', ',')

# Get value type
def regType(valueRaw):
    value = valueRaw.strip()

    if value[0] == '"':
        searchPattern = re.compile('%[0-9a-z\(\)_]+%', re.IGNORECASE)

        if searchPattern.search(value):
            # REG_EXPAND_SZ
            return procExpand(value)

        # REG_SZ
        return value

    elif value[0:2] == '0x':
        # REG_DWORD
        return procDword(value)

    else:
        valueNoSpace = value.replace(' ', '')

        if len(valueNoSpace) == 8:
            # REG_BINARY
            return procHex('binary', value)

        elif len(valueNoSpace) == 16:
            # REG_QWORD
            return procHex('qword', value)

        elif len(valueNoSpace) > 16:
            # REG_MULTI_SZ
            return procHex('multi', value)
        else:
            # Sometimes something like '(NULL!)' happens. I don't know why and I'm
            # not sure what the proper response should be. For now, there is this.
            return '""'

# Process chunks of values
def procChunks(output, strInput, bol, eol, splitAt):
    while len(strInput) > 0:
        if len(strInput) > splitAt:
            nextLineSplit = strInput[:splitAt].rsplit(',', 1)
            output += bol + nextLineSplit[0] + eol
            strInput = nextLineSplit[1] + strInput[splitAt:]
        else:
            output += bol + strInput
            strInput = ''

    return output

# Format lines for readability
def formatLines(strInput):
    # Is input eligible for splitting
    value = strInput.split('=', 1)

    # Check for default key value
    if value[0] == '""':
        value[0] = '@'

    if value[1][0] != '"' and len(strInput) > 80:
        firstLine = ''
        restLines = ''
        bol = '  '
        eol = ',\\\n'

        # Check for a really long key
        if len(value[0]) > 63:
            firstComma = value[1].split(',', 1)
            firstLine = value[0] + firstComma[0] + eol
            restLines = firstComma[1]
        else:
            firstLineSplit = strInput[:79].rsplit(',', 1)
            firstLine = firstLineSplit[0] + eol
            restLines = firstLineSplit[1] + strInput[79:]

        # Process rest of values
        output = firstLine

        return procChunks(firstLine, restLines, bol, eol, 75)

    return value[0] + '=' + value[1]

# Function to add and remove keys
def addDelKeys(regPack, regString, action):
    addUndoRedo = 'regRedo'
    delUndoRedo = 'regUndo'

    if action == 'del':
        addUndoRedo = 'regUndo'
        delUndoRedo = 'regRedo'

    regPack[addUndoRedo]['[' + regString + ']']
    regPack[delUndoRedo]['[-' + regString + ']']

    return regPack

# Function to add and remove values
def addDelValues(regPack, regString, action):
    addUndoRedo = 'regRedo'
    delUndoRedo = 'regUndo'
    getKeyValue = regString.split(': ', 1)
    getRegKeyPath = getKeyValue[0].rsplit('\\', 1)
    delPath = '[-' + getRegKeyPath[0] + ']'
    formKeyValue = formatLines('"' + getRegKeyPath[1] + '"=' + regType(getKeyValue[1]))

    if action == 'del':
        addUndoRedo = 'regUndo'
        delUndoRedo = 'regRedo'

    regPack[addUndoRedo]['[' + getRegKeyPath[0] + ']'].append(formKeyValue)

    # Only delete values if the key is not going to be deleted
    if delPath not in regPack[delUndoRedo]:
        regPack[delUndoRedo]['[' + getRegKeyPath[0] + ']'].append('"' + getRegKeyPath[1] + '"=-')

    return regPack

# Function to modify values
def modifyValues(regPack, regString, lineCounter):
    getKeyValue = regString.split(': ', 1)
    getRegKeyPath = getKeyValue[0].rsplit('\\', 1)
    redoUndo = 'regUndo'
    formKeyValue = formatLines('"' + getRegKeyPath[1] + '"=' + regType(getKeyValue[1]))

    if lineCounter % 2 == 0:
        redoUndo = 'regRedo'

    regPack[redoUndo]['[' + getRegKeyPath[0] + ']'].append(formKeyValue)

    return regPack

# Get registry abbreviations
def getRegAb():
    regSubAbDict = {
        'HKCR': 'HKEY_CLASSES_ROOT',
        'HKCU': 'HKEY_CURRENT_USER',
        'HKLM': 'HKEY_LOCAL_MACHINE',
        'HKU': 'HKEY_USERS',
        'HKCC': 'HKEY_CURRENT_CONFIG'
    }

    return regSubAbDict

# Translate registry abbreviation to subtree name
def regSubtreeAb(regString):
    regSubtreeAbDict = getRegAb()
    regSubtree = regString.split('\\', 1)

    return regSubtreeAbDict[regSubtree[0]] + '\\' + regSubtree[1]

# Check if valid raw line (before converting from abbreviation)
def isValidRawLine(regString):
    if '\\' in regString:
        regSubtreeAbDict = getRegAb()
        regSubtree = regString.split('\\', 1)

        if regSubtree[0] in regSubtreeAbDict:
            return True

    return False

# Write CRUD reg keys depending on current mode
def sortContentsBy(regPack, mode, line, sectionCounter):
    if mode == 'keysAdded':
        return addDelKeys(regPack, regSubtreeAb(line), 'add')
    elif mode == 'keysDeleted':
        return addDelKeys(regPack, regSubtreeAb(line), 'del')
    elif mode == 'valuesAdded':
        return addDelValues(regPack, regSubtreeAb(line), 'add')
    elif mode == 'valuesModified':
        return modifyValues(regPack, regSubtreeAb(line), sectionCounter)
    elif mode == 'valuesDeleted':
        return addDelValues(regPack, regSubtreeAb(line), 'del')

# Include line or unnecessary
def includeLine(excludeMode, mode, line, stripLine):
    separator = '----------------------------------'

    # SELECT    lines if there is content in the line
    # AND       that content does not include the standard regshot dashes
    # AND       mode != header / footer / the mode we want to exclude
    # AND       line is not a section header
    if (
            line.strip() and
            separator not in line and
            mode != excludeMode and
            mode.lower() not in stripLine
       ):

        return True

# Change CRUD status by header lines
def setModeBy(lstModes, setMode, stripLine):
    for mode in lstModes:
        if mode.lower() in stripLine:
            setMode = mode
            break
        elif 'totalchanges' in stripLine:
            setMode = lstModes[0]

    return setMode

# Test output
def testOutput(regPack):
    for x in regPack['regRedo']:
        print(x)
        for y in regPack['regRedo'][x]:
            print(y)

    for x in regPack['regUndo']:
        print(x)
        for y in regPack['regUndo'][x]:
            print(y)

# Check for existing file with the same name
def checkExisting(fileName):
    regFiles = getDirFiles('*.reg', 'stripExt')
    escFileName = re.escape(fileName)
    searchPattern = re.compile(escFileName + '_rtr_\d+$')
    foundFiles = []

    for name in regFiles:
        if searchPattern.search(name):
            foundFiles.append(int(name.rsplit('_', 1)[1]))

    if foundFiles:
        foundFiles.sort(reverse = True)
        newNum = foundFiles[0] + 1

        return fileName + '_rtr_' + str(newNum)

    return fileName + '_rtr_1'

# Create a new file
def writeDictToFile(regPack, fileName, redoUndo, header):
    safeFileName = checkExisting(fileName) + '.reg'
    newFile = open(safeFileName, 'w')

    print(header + '\n', file = newFile)

    for regKey in regPack[redoUndo]:
        print(regKey, file = newFile)
        for regValue in regPack[redoUndo][regKey]:
            print(u'regValue', file = newFile)
    newFile.close()

    return safeFileName

# Write to Redo and Undo reg files
def writeRedoUndo(regPack):
    header = 'Windows Registry Editor Version 5.00'

    if regPack['regRedo']:
        redoFileName = 'redo_' + getFullPath('onlyName')
        redoFileNameSafe = writeDictToFile(regPack, redoFileName, 'regRedo', header)
        print('Created \'' + redoFileNameSafe + '\' file.')

    if regPack['regUndo']:
        undoFileName = 'undo_' + getFullPath('onlyName')
        undoFileNameSafe = writeDictToFile(regPack, undoFileName, 'regUndo', header)
        print('Created \'' + undoFileNameSafe + '\' file.')

# A potentially hackish way to parse broken lines together
# Delays calling function until we see that the next line is a complete line
def parseLines(regPack, setMode, cleanLine, sectionCounter):
    # Original function call
    # regPack = sortContentsBy(regPack, setMode, cleanLine, sectionCounter)
    isValidLine = isValidRawLine(cleanLine)

    # What to do with current and past lines
    if not regPack['sectionLines'] and isValidLine:
        # If the queue is empty and the current line is valid,
        # then add it to the queue and take no further action
        regPack['sectionLines']['setMode'] = setMode
        regPack['sectionLines']['cleanLine'] = cleanLine
        regPack['sectionLines']['sectionCounter'] = sectionCounter
    elif regPack['sectionLines'] and not isValidLine:
        # If the current line is not valid then add to previous line,
        # and take no further action (do not call sort)

        # Insert space for trimmed invalid lines cut evenly (_00_ not 0_0)
        if ' ' not in cleanLine[:2]:
            cleanLine = ' ' + cleanLine

        regPack['sectionLines']['cleanLine'] += cleanLine
    elif regPack['sectionLines'] and isValidLine:
        # If the current line is valid then process the previous line,
        # and replace the current line with the new line
        regPack = sortContentsBy(
            regPack,
            regPack['sectionLines']['setMode'],
            regPack['sectionLines']['cleanLine'],
            regPack['sectionLines']['sectionCounter']
        )
        regPack['sectionLines']['setMode'] = setMode
        regPack['sectionLines']['cleanLine'] = cleanLine
        regPack['sectionLines']['sectionCounter'] = sectionCounter

    return regPack

# Now open the entire file with correct encoding
def openFileBy(targetFile, encoding, debugOption):
    # Choose encoding
    encDict = {'ansi': 'ascii', 'unicode': 'utf-16-le'}
    useEnc = encDict[encoding.lower()]

    try:
        with codecs.open(targetFile, 'r', useEnc) as openFile:
            # Set list modes and counter
            lstModes = [
                'headerFooter',
                'keysAdded',
                'keysDeleted',
                'valuesAdded',
                'valuesDeleted',
                'valuesModified'
            ]
            setMode = lstModes[0]
            sectionCounter = 1

            # Create 'redo' and 'undo' dictionaries packed together for ease of passing around
            # Also build section lines list to catch broken lines
            regPack = {
                'regRedo': defaultdict(list),
                'regUndo': defaultdict(list),
                'sectionLines': defaultdict(str)
            }

            print('Processing file...')

            for line in openFile:
                cleanLine = ' '.join(line.split())
                stripLine = cleanLine.replace(' ', '').lower()
                curMode = setModeBy(lstModes, setMode, stripLine)

                # Check if mode has changed and if so reset line count
                if setMode != curMode:
                    setMode = curMode
                    sectionCounter = 1

                # If the line should be included
                if includeLine(lstModes[0], setMode, cleanLine, stripLine):
                    regPack = parseLines(regPack, setMode, cleanLine, sectionCounter)
                    sectionCounter += 1
            else:
                # To test output use
                # testOutput(regPack)

                # Writing to two new files (redo and undo)
                writeRedoUndo(regPack)
    except Exception as e:
        if debugOption:
            doDebug(e, debugOption)
        else:
            print('Could not open the file.')

# Test if there is a file specified
def fileSpec():
    if len(sys.argv) > 1:
        return True
    else:
        return False

# Test if there is a file specified
def debugSpec():
    if len(sys.argv) > 2:
        return True
    else:
        return False

# Check to make sure this is a valid file and if so get the type (ANSI / Unicode)
def checkFile():
    targetFile = getFullPath()
    searchPattern = re.compile('regshot.*(unicode|ansi)', re.IGNORECASE)
    debugOption = '' if not debugSpec() else sys.argv[2]

    # Try to open file
    try:
        with open(targetFile, 'r') as peekFile:
            searchMax = 10
            searchCount = searchMax

            for line in peekFile:
                noSpaces = line.replace('\x00', '')

                if re.search(searchPattern, noSpaces):
                    encoding = re.search(searchPattern, noSpaces).group(1)

                    print('Opening file as ' + encoding + '.')
                    openFileBy(targetFile, encoding, debugOption)
                    break
                elif searchCount > 0:
                    searchCount -= 1
                else:
                    print('This doesn\'t look like a regshot file.')
                    print(
                        'Searched the first ' + str(searchMax) + ' lines and didn\'t '
                        'find a header similar to this: Regshot 1.9.0 x64 ANSI'
                    )
                    break

    except Exception as e:
        if debugOption:
            doDebug(e, debugOption)
        else:
            print(
                'Something went wrong. Usually this means the file could not be '
                'found or is not a valid regshot file.'
            )

# Main program
def main():
    if fileSpec():
        checkFile()
    else:
        print('Select a file by passing its name and extension as a command line parameter.')
        print('Example: ' + os.path.basename(__file__) + ' text_file.txt')

# Run main program
if __name__ == '__main__':
    main()
