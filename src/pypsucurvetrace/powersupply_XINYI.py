"""
Python class to control XinYi (XY) XY-xxxx* power supplies
"""

# Useful information about RIDEN Modbus registers and other details: https://github.com/ShayBox/Riden
# The XinYi Modbus implementation is largely the same, and if anything is different, it's not on purpose.

import time
import minimalmodbus
from pypsucurvetrace.curvetrace_tools import get_logger

# set up logger:
logger = get_logger('powersupply_XINYI')

# Python dictionary of known XinYi Electronics (XY-....) power supply models 
# 						(Vmin, Vmax, Imax, Pmax,   Vres,   Ires, VoffMax,IoffMax,MaxSettleTime)

XINYI_SPECS = {
       #"RD6006":	    ( 0.0, 60.0,  6.0,  360,  0.001,  0.001,  0.0, 0.0, 0.3 ) , # not confirmed
       #"RD6006P":	    ( 0.0, 60.0,  6.0,  360,  0.001,  0.0001, 0.0, 0.0, 1.5 ) , # confirmed working
       #"RD6012":	    ( 0.0, 60.0, 12.0,  720,  0.001,  0.001,  0.0, 0.0, 0.3 ) , # not confirmed
       #"RD6012P_6A":	( 0.0, 60.0,  6.0,  360,  0.001,  0.0001, 0.0, 0.0, 1.8 ) , # 6012P in low-current mode (0..6A at 0.1 mA resolution), confirmed working
       #"RD6012P_12A":	( 0.0, 60.0, 12.0,  720,  0.001,  0.001,  0.0, 0.0, 1.8 ) , # 6012P in high-current mode (0..12A at 1 mA resolution), confirmed working
        "XY-6015L":     ( 0.0, 60.0, 15.0,  900,  0.010,  0.010,  0.0, 0.0, 1.0 ) ,
        "XY-6020L":     ( 0.0, 60.0, 20.0, 1200,  0.010,  0.010,  0.0, 0.0, 1.0 ) 
}

### Important to note: These memory addresses are all +30 relative to their actual hex memory location, because they're decimal versions.
### Subsequent profiles (Cd1 and up) have their memory locations at +0x0010h i.e. Cd0's 0x0052 becomes Cd1's 0x0062
### But Cd0 is most important: It's the "runtime/current" memory register set that serves as whereto settings are "loaded" if recalled from any other memory preset.
### Recalling is done by writing the profile number ranging 1 to 9 to 0x001D. This will write the chosen profile to Cd0's offset (0x0050)

MEMORY_PROFILES_XINYI = {
"Cd0": {
        "V-SET":    80,  # 0x0050
        "I-SET":    81,  # 0x0051
        "S-LVP":    82,  # 0x0052
        "S-OVP":    83,  # 0x0053
        "S-OCP":    84,  # 0x0054
        "S-OPP":    85,  # 0x0055
        "S-OHP_H":  86,  # 0x0056
        "S-OHP_M":  87,  # 0x0057
        "S-OAH_L":  88,  # 0x0058
        "S-OAH_H":  89,  # 0x0059
        "S-OWH_L":  90,  # 0x005A
        "S-OWH_H":  91,  # 0x005B
        "S-OTP":    92,  # 0x005C
        "S-INI":    93   # 0x005D
    },
    "Cd1": {
        "V-SET":    96,  # 0x0060
        "I-SET":    97,  # 0x0061
        "S-LVP":    98,  # 0x0062
        "S-OVP":    99,  # 0x0063
        "S-OCP":    100, # 0x0064
        "S-OPP":    101, # 0x0065
        "S-OHP_H":  102, # 0x0066
        "S-OHP_M":  103, # 0x0067
        "S-OAH_L":  104, # 0x0068
        "S-OAH_H":  105, # 0x0069
        "S-OWH_L":  106, # 0x006A
        "S-OWH_H":  107, # 0x006B
        "S-OTP":    108, # 0x006C
        "S-INI":    109  # 0x006D
    },
    "Cd2": {
        "V-SET":    112, # 0x0070
        "I-SET":    113, # 0x0071
        "S-LVP":    114, # 0x0072
        "S-OVP":    115, # 0x0073
        "S-OCP":    116, # 0x0074
        "S-OPP":    117, # 0x0075
        "S-OHP_H":  118, # 0x0076
        "S-OHP_M":  119, # 0x0077
        "S-OAH_L":  120, # 0x0078
        "S-OAH_H":  121, # 0x0079
        "S-OWH_L":  122, # 0x007A
        "S-OWH_H":  123, # 0x007B
        "S-OTP":    124, # 0x007C
        "S-INI":    125  # 0x007D
    },
    "Cd3": {
        "V-SET":    128, # 0x0080
        "I-SET":    129, # 0x0081
        "S-LVP":    130, # 0x0082
        "S-OVP":    131, # 0x0083
        "S-OCP":    132, # 0x0084
        "S-OPP":    133, # 0x0085
        "S-OHP_H":  134, # 0x0086
        "S-OHP_M":  135, # 0x0087
        "S-OAH_L":  136, # 0x0088
        "S-OAH_H":  137, # 0x0089
        "S-OWH_L":  138, # 0x008A
        "S-OWH_H":  139, # 0x008B
        "S-OTP":    140, # 0x008C
        "S-INI":    141  # 0x008D
    },
    "Cd4": {
        "V-SET":    144, # 0x0090
        "I-SET":    145, # 0x0091
        "S-LVP":    146, # 0x0092
        "S-OVP":    147, # 0x0093
        "S-OCP":    148, # 0x0094
        "S-OPP":    149, # 0x0095
        "S-OHP_H":  150, # 0x0096
        "S-OHP_M":  151, # 0x0097
        "S-OAH_L":  152, # 0x0098
        "S-OAH_H":  153, # 0x0099
        "S-OWH_L":  154, # 0x009A
        "S-OWH_H":  155, # 0x009B
        "S-OTP":    156, # 0x009C
        "S-INI":    157  # 0x009D
    },
    "Cd5": {
        "V-SET":    160, # 0x00A0
        "I-SET":    161, # 0x00A1
        "S-LVP":    162, # 0x00A2
        "S-OVP":    163, # 0x00A3
        "S-OCP":    164, # 0x00A4
        "S-OPP":    165, # 0x00A5
        "S-OHP_H":  166, # 0x00A6
        "S-OHP_M":  167, # 0x00A7
        "S-OAH_L":  168, # 0x00A8
        "S-OAH_H":  169, # 0x00A9
        "S-OWH_L":  170, # 0x00AA
        "S-OWH_H":  171, # 0x00AB
        "S-OTP":    172, # 0x00AC
        "S-INI":    173  # 0x00AD
    },
    "Cd6": {
        "V-SET":    176, # 0x00B0
        "I-SET":    177, # 0x00B1
        "S-LVP":    178, # 0x00B2
        "S-OVP":    179, # 0x00B3
        "S-OCP":    180, # 0x00B4
        "S-OPP":    181, # 0x00B5
        "S-OHP_H":  182, # 0x00B6
        "S-OHP_M":  183, # 0x00B7
        "S-OAH_L":  184, # 0x00B8
        "S-OAH_H":  185, # 0x00B9
        "S-OWH_L":  186, # 0x00BA
        "S-OWH_H":  187, # 0x00BB
        "S-OTP":    188, # 0x00BC
        "S-INI":    189  # 0x00BD
    },
    "Cd7": {
        "V-SET":    200, # 0x00C0
        "I-SET":    201, # 0x00C1
        "S-LVP":    202, # 0x00C2
        "S-OVP":    203, # 0x00C3
        "S-OCP":    204, # 0x00C4
        "S-OPP":    205, # 0x00C5
        "S-OHP_H":  206, # 0x00C6
        "S-OHP_M":  207, # 0x00C7
        "S-OAH_L":  208, # 0x00C8
        "S-OAH_H":  209, # 0x00C9
        "S-OWH_L":  210, # 0x00CA
        "S-OWH_H":  211, # 0x00CB
        "S-OTP":    212, # 0x00CC
        "S-INI":    213  # 0x00CD
    },
    "Cd8": {
        "V-SET":    216, # 0x00D0
        "I-SET":    217, # 0x00D1
        "S-LVP":    218, # 0x00D2
        "S-OVP":    219, # 0x00D3
        "S-OCP":    220, # 0x00D4
        "S-OPP":    221, # 0x00D5
        "S-OHP_H":  222, # 0x00D6
        "S-OHP_M":  223, # 0x00D7
        "S-OAH_L":  224, # 0x00D8
        "S-OAH_H":  225, # 0x00D9
        "S-OWH_L":  226, # 0x00DA
        "S-OWH_H":  227, # 0x00DB
        "S-OTP":    228, # 0x00DC
        "S-INI":    229  # 0x00DD
    },
    "Cd9": {
        "V-SET":    232, # 0x00E0
        "I-SET":    233, # 0x00E1
        "S-LVP":    234, # 0x00E2
        "S-OVP":    235, # 0x00E3
        "S-OCP":    236, # 0x00E4
        "S-OPP":    237, # 0x00E5
        "S-OHP_H":  238, # 0x00E6
        "S-OHP_M":  239, # 0x00E7
        "S-OAH_L":  240, # 0x00E8
        "S-OAH_H":  241, # 0x00E9
        "S-OWH_L":  242, # 0x00EA
        "S-OWH_H":  243, # 0x00EB
        "S-OTP":    244, # 0x00EC
        "S-INI":    245  # 0x00ED
    }
}

YinXi_TIMEOUT = 1.0

MAX_COMM_ATTEMPTS = 10

def _XinYi_debug(s):
    sys.stdout.write(s)
    sys.stdout.flush()

# XinYi:
#    .output(state)
#    .voltage(voltage)
#    .current(current)
#    .reading()
#    .VMIN
#    .VMAX
#    .IMAX
#    .VRESSET
#    .IRESSET
#    .VRESREAD
#    .IRESREAD
#    .VOFFSETMAX
#    .VOFFSETMAX
#    .IOFFSETMAX
#    .MAXSETTLETIME
#    .READIDLETIME
#    .MODEL

class XINYI(object):
    """
    Class for XinYi (XY) power supply
    """

    def __init__(self, port, baud=57600, debug=False):
        '''
        PSU(port)
        port : serial port (string, example: port = '/dev/serial/by-id/XYZ_123_abc')
        baud : baud rate of serial port (check the settings at the XY PSU unit, see table for reference)
        debug: flag for debugging info (bool)
        '''
        
        self._debug = bool(debug)
        
        # open and configure ModBus/serial port:
        try:
            self._instrument = minimalmodbus.Instrument(port=port, slaveaddress=1)
            self._instrument.serial.baudrate = baud
            self._instrument.serial.timeout = 1.0
            time.sleep(0.2) # wait a bit unit the port is really ready
        except:
            raise RuntimeError('Could not connect to XinYi (XY) power supply at ' + port)


        # determine model / type:
        try:
            # OCP and OVP max values:
            OCP_max = OVP_max = None
            #mdl = self._get_register(0)
            mdl = True

            if mdl == True:
                # XY-6015L
                self.MODEL = 'XY-6015L'
                OVP_max = 61.0
                OCP_max = 15.0
 
            else:
                # unknown XinYi model:
                logger.warning ( 'Unknown XinYi model ID: ' + mdl )
                self.MODEL = '<unknown>'

            self.VMIN          = XINYI_SPECS[self.MODEL][0]
            self.VMAX          = XINYI_SPECS[self.MODEL][1]
            self.IMAX          = XINYI_SPECS[self.MODEL][2]
            self.PMAX          = XINYI_SPECS[self.MODEL][3]
            self.VRESSET       = XINYI_SPECS[self.MODEL][4]
            self.VRESREAD      = XINYI_SPECS[self.MODEL][4]
            self.IRESSET       = XINYI_SPECS[self.MODEL][5]
            self.IRESREAD      = XINYI_SPECS[self.MODEL][5]
            self.VOFFSETMAX    = XINYI_SPECS[self.MODEL][6]
            self.IOFFSETMAX    = XINYI_SPECS[self.MODEL][7]
            self.MAXSETTLETIME = XINYI_SPECS[self.MODEL][8]
            self.READIDLETIME  = self.MAXSETTLETIME/5

        except KeyError:
            raise RuntimeError('Unknown XiNYi powersupply type/model ' + self.MODEL)
        except:
            raise RuntimeError('Could not determine XinYi powersupply type/model')
            
        # set over-voltage and over-current settings to max. values (to avoid them from unintended limiting):

        # Basic structure of a two-level Python dictionary
        # Parent element containing nine unique versions of a specific list structure

        MEM = MEMORY_PROFILES_XINYI

        if ( OCP_max is None ) or ( OVP_max is None ):
            logger.warning( 'Cannot adjust OVP and OCP limits of the ' + self.MODEL + ' power supply.' )
        else:
            logger.info ( 'Adjusting OVP to ' + str(OVP_max) + ' V and and OCP to ' + str(OCP_max) + ' A.' )
            logger.info (f"Using registers MEM['Cd0']['S-OVP'] ({MEM['Cd0']['S-OVP']}) and MEM['Cd0']['S-OCP'] ({MEM['Cd0']['S-OCP']}) for this.")
            
            mul_U = self._voltage_multiplier()
            mul_I = self._current_multiplier()
            
            self._set_register(MEM['Cd0']['S-OVP'], OVP_max*mul_U)
            self._set_register(MEM['Cd0']['S-OCP'], OCP_max*mul_I)


    def _set_register(self, register, value):
        k = 1
        while k <= MAX_COMM_ATTEMPTS:
            try:
                self._instrument.write_register(register, int(value))
                break # break from the loop if communication was successful
            except:
                k += 1
                pass # keep trying
        if k > MAX_COMM_ATTEMPTS:
            raise RuntimeError('Communication with XinYi ' + self.MODEL + ' at ' + self._instrument.serial.port + ' failed.')
            

    def _get_register(self, register):
        value = None
        k = 1
        while k <= MAX_COMM_ATTEMPTS:
            try:
                value = self._instrument.read_register(register)
                break # break from the loop if communication was successful
            except:
                k += 1
                pass # keep trying
        if k > MAX_COMM_ATTEMPTS:
            raise RuntimeError('Communication with XinYi ' + self.MODEL + ' at ' + self._instrument.serial.port + ' failed.')
 
        return value


    def _get_N_registers(self, register_start, N):
        value = None
        k = 1
        while k <= MAX_COMM_ATTEMPTS:
            try:
                values = self._instrument.read_registers(register_start, N)
                break # break from the loop if communication was successful
            except:
                k += 1
                pass # keep trying
        if k > MAX_COMM_ATTEMPTS:
            raise RuntimeError('Communication with XinYi ' + self.MODEL + ' at ' + self._instrument.serial.port + ' failed.')
 
        return values


    def output(self, state):
        """
        enable/disable the PS output
        """
        state = int(bool(state))
        self._set_register(18, state)


    def voltage(self, voltage):
        """
        set voltage: silently saturates at VMIN and VMAX
        """
        if voltage > self.VMAX:
            voltage = self.VMAX
        if voltage < self.VMIN:
            voltage = self.VMIN
            
        self._set_register(8, round(voltage*self._voltage_multiplier()))
        
        ## time.sleep(0.5)
        
        u = self.reading()
        

    def current(self, current):
        """
        set current: silently saturates at IMIN and IMAX
        """
        
        if current > self.IMAX:
            current = self.IMAX
        if current < 0.0:
            current = 0.0
        
        self._set_register(9, round(current*self._current_multiplier()))


    def reading(self):
        """
        read applied output voltage and current and if PS is in "CV" or "CC" mode
        """
        
        # read voltage and current registers:
        V_mult = self._voltage_multiplier()
        I_mult = self._current_multiplier()
        u = self._get_N_registers(10,2)
        V = u[0] / V_mult
        I = u[1] / I_mult
        
        # check register 17 (CV or CC?)
        if self._get_register(17) == 1:
            S = 'CC'
        else:
            S = 'CV'

        return (V, I, S)


    def _voltage_multiplier(self):
        """
        return multiplier for voltage register value
        """
        
        multi = 1.0 / float(XINYI_SPECS[self.MODEL][4])

        return multi
        

    def _current_multiplier(self):
        """
        return multiplier for current register value
        """
        
        multi = 1.0 / float(XINYI_SPECS[self.MODEL][5])
            
        return multi
        
        
    """ def _current_multiplier_nadanixdabum(self):
        # return multiplier for current register value
        
        if 'RIDEN6012P' in self.MODEL:
            if self._get_register(20) == 0:
                multi = 10000.0
            else:
                multi = 1000.0
                
        else:
            multi = 1.0 / float(XINYI_SPECS[self.MODEL][5])
            
        return multi
 """