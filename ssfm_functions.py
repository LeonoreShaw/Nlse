# -*- coding: utf-8 -*-
"""
Created on Fri Dec  9 10:23:48 2022

@author: okrarup
"""

import numpy as np
from scipy.fftpack import fft, ifft, fftshift, ifftshift, fftfreq
from scipy.signal import find_peaks

import matplotlib.pyplot as plt
from matplotlib import cm

import os
from IPython.lib.display import isdir

import time
from datetime import datetime

import pickle

global pi; pi=np.pi 


def getFreqRangeFromTime(time):
    return fftshift(fftfreq(len(time), d=time[1]-time[0]))

def getPhase(pulse):
    phi=np.unwrap(np.angle(pulse)) #Get phase starting from 1st entry
    phi=phi-phi[int(len(phi)/2)]   #Center phase on middle entry
    return phi    


def getChirp(time,pulse):
    phi=getPhase(pulse)
    dphi=np.diff(phi ,prepend = phi[0] - (phi[1]  - phi[0]  ),axis=0) #Change in phase. Prepend to ensure consistent array size 
    dt  =np.diff(time,prepend = time[0]- (time[1] - time[0] ),axis=0) #Change in time.  Prepend to ensure consistent array size

    return -1.0/(2*pi)*dphi/dt #Chirp = - 1/(2pi) * d(phi)/dt
    
    


class timeFreq_class:
    def __init__(self,N,dt):
        self.number_of_points=N
        self.time_step=dt
        t=np.linspace(0,N*dt,N)
        self.t=t-np.mean(t)
        self.tmin=self.t[0]
        self.tmax=self.t[-1]
        
        self.f=getFreqRangeFromTime(self.t)
        self.fmin=self.f[0]
        self.fmax=self.f[-1]
        self.freq_step=self.f[1]-self.f[0]

        self.describe_config()
        
    def describe_config(self,destination = None):
        print(" ### timeFreq Configuration Parameters ###" , file = destination)
        print(f"  Number of points = {self.number_of_points}", file = destination)
        print(f"  Start time, tmin = {self.tmin*1e12:.3f}ps", file = destination)
        print(f"  Stop time, tmax = {self.tmax*1e12:.3f}ps", file = destination)
        print(f"  Time resolution, dt = {self.time_step*1e12:.3f}ps", file = destination)
        print("  ", file = destination)
        print(f"  Start frequency= {self.fmin/1e12:.3f}THz", file = destination)
        print(f"  Stop frequency = {self.fmax/1e12:.3f}THz", file = destination)
        print(f"  Frequency resolution= {self.freq_step/1e6:.3f}MHz", file = destination)
        print( "   ", file = destination)
        


        
    
        
#Function returns pulse power or spectrum PSD
def getPower(amplitude):
    return np.abs(amplitude)**2  

#Function gets the energy of a pulse pulse or spectrum by integrating the power
def getEnergy(time_or_frequency,amplitude):
    return np.trapz(getPower(amplitude),time_or_frequency)

#TODO: Add support for different carrier frequencies. Hint: Multiply by complex exponential!
#TODO: Add support for pre-chirped pulses. 
def GaussianPulse(time,amplitude,duration,offset,chirp,order,carrier_freq_Hz):
    assert 1 <= order, f"Error: Order of gaussian pulse is {order}. Must be >=1"
    return amplitude*np.exp(- (1+1j*chirp)/2*((time-offset)/(duration))**(2*np.floor(order)))*np.exp(-1j*2*pi*carrier_freq_Hz*time)

def squarePulse(time,amplitude,duration,offset,chirp,carrier_freq_Hz):
    return GaussianPulse(time,amplitude,duration,offset,chirp,100,carrier_freq_Hz)


#Define sech pulse
def sechPulse(time,amplitude,duration,offset,chirp,carrier_freq_Hz):
    return amplitude/np.cosh((time-offset)/duration)*np.exp(- (1j*chirp)/2*((time-offset)/(duration))**2)*np.exp(-1j*2*pi*carrier_freq_Hz*time)


#Define function for adding white noise
def noise_ASE(time,amplitude):
    randomAmplitudes=np.random.normal(loc=0.0, scale=amplitude, size=len(time))*(1+0j)
    randomPhases = np.random.uniform(-pi,pi, len(time))
    return randomAmplitudes*np.exp(1j*randomPhases)   


def getPulse(time,amplitude,duration,offset,chirp,carrier_freq_Hz,pulseType,order,noiseAmplitude):
    
    noise = noise_ASE(time,noiseAmplitude)
    
    if pulseType.lower()=="gaussian":
        return GaussianPulse(time,amplitude,duration,offset,chirp,order,carrier_freq_Hz)+noise
    
    if pulseType.lower()=="sech":
        return sechPulse(time,amplitude,duration,offset,chirp,carrier_freq_Hz)+noise
    
    if pulseType.lower()=="square":
        return squarePulse(time,amplitude,duration,offset,chirp,carrier_freq_Hz)+noise
    
    if pulseType.lower()=="custom":
        return noise


def getSpectrumFromPulse(time,pulse_amplitude):
    pulseEnergy=getEnergy(time,pulse_amplitude) #Get pulse energy
    f=getFreqRangeFromTime(time) 
    dt=time[1]-time[0]
    
    spectrum_amplitude=fftshift(fft(pulse_amplitude))*dt #Take FFT and do shift
    spectrumEnergy=getEnergy(f, spectrum_amplitude) #Get spectrum energy
    
    err=np.abs((pulseEnergy/spectrumEnergy-1))
    
    assert( err<1e-7 ), f'ERROR = {err}: Energy changed when going from Pulse to Spectrum!!!' 
    
    return spectrum_amplitude



#Equivalent function for getting time base from frequency range
def getTimeFromFrequency(frequency):  
    return fftshift(fftfreq(len(frequency), d=frequency[1]-frequency[0]))


#Equivalent function for getting pulse from spectrum
def getPulseFromSpectrum(frequency,spectrum_amplitude):
    
    spectrumEnergy=getEnergy(frequency, spectrum_amplitude)
    
    time = getTimeFromFrequency(frequency)
    dt = time[1]-time[0]
     
    pulse = ifft(ifftshift(spectrum_amplitude))/dt
    pulseEnergy = getEnergy(time, pulse)
    
    err=np.abs((pulseEnergy/spectrumEnergy-1))

    assert( err<1e-7   ), f'ERROR = {err}: Energy changed when going from Spectrum to Pulse!!!' 
    
    return pulse

#Equivalent function for generating a Gaussian spectrum
def GaussianSpectrum(frequency,amplitude,bandwidth,carrier_freq_Hz):
    time = getTimeFromFrequency(frequency)
    return getSpectrumFromPulse(time, GaussianPulse(time, amplitude, 1/bandwidth, 0,0,1,carrier_freq_Hz))


class Fiber_class:
    def __init__(self,L,gamma,beta2,alpha_dB_per_m):
      self.Length=L
      self.gamma=gamma
      self.beta2=beta2
      self.alpha_dB_per_m=alpha_dB_per_m
      self.alpha_Np_per_m = self.alpha_dB_per_m*np.log(10)/10.0 #Loss coeff is usually specified in dB/km, but Nepers/km is more useful for calculations
      #TODO: Make alpha frequency dependent.  
      self.describe_fiber()
      
    def describe_fiber(self,destination = None):
        print(' ### Characteristic parameters of fiber: ###', file = destination)
        print(f'Fiber Length \t\t= {self.Length/1e3}km ', file = destination)
        print(f'Fiber gamma \t\t= {self.gamma}/W/m ', file = destination)
        print(f'Fiber beta2 \t\t= {self.beta2}s**2/m ', file = destination)
        print(f'Fiber alpha_dB_per_m \t= {self.alpha_dB_per_m}', file = destination)
        print(f'Fiber alpha_Np_per_m \t= {self.alpha_Np_per_m}', file = destination)
        print(' ', file = destination)
      
class input_signal_class:
    def __init__(self,timeFreq:timeFreq_class,peak_amplitude,duration,offset,chirp,carrier_freq_Hz,pulseType,order,noiseAmplitude):

        
        self.timeFreq=timeFreq
        self.amplitude = getPulse(self.timeFreq.t,peak_amplitude,duration,offset,chirp,carrier_freq_Hz,pulseType,order,noiseAmplitude)
        

        if getEnergy(self.timeFreq.t, self.amplitude) == 0.0:
            self.spectrum = np.copy(self.amplitude)  
        else:
            self.spectrum = getSpectrumFromPulse(self.timeFreq.t,self.amplitude)   
        
        self.Pmax=np.max(getPower(self.amplitude))
        self.duration=duration
        self.offset=offset
        self.chirp=chirp
        self.carrier_freq_Hz=carrier_freq_Hz
        self.pulseType=pulseType
        self.order=order
        self.noiseAmplitude=noiseAmplitude
        
        self.describe_input_signal()
        
    def describe_input_signal(self,destination = None):
        print(" ### Input Signal Parameters ###" , file = destination)
        print(f"  Pmax = {self.Pmax:.3f}W", file = destination)
        print(f"  Duration = {self.duration*1e12:.3f}ps", file = destination)
        print(f"  Offset = {self.offset*1e12:.3f}ps", file = destination)
        print(f"  Chirp = {self.chirp:.3f}", file = destination)
        print(f"  Carrier_freq = {self.carrier_freq_Hz/1e12}THz", file = destination)
        print(f"  pulseType = {self.pulseType}", file = destination)
        print(f"  order = {self.order}", file = destination)
        print(f"  noiseAmplitude = {self.noiseAmplitude:.3f}sqrt(W)", file = destination)
        
        print( "   ", file = destination)


def zstep_NL(z,fiber:Fiber_class, input_signal:input_signal_class,stepmode,stepSafetyFactor):
    
    if fiber.gamma == 0.0:
        return fiber.Length
    
    if fiber.beta2 == 0.0:
        return fiber.Length
    
    
    
    if stepmode.lower()=="cautious":
        return np.abs(fiber.beta2)*pi/(fiber.gamma*input_signal.Pmax*input_signal.duration)**2*np.exp(2*fiber.alpha_Np_per_m*z)/stepSafetyFactor
    
    if stepmode.lower()=="approx":
        return np.abs(fiber.beta2)*pi/(fiber.gamma*input_signal.Pmax)**2/(input_signal.duration*input_signal.timeFreq.time_step)*np.exp(2*fiber.alpha_Np_per_m*z)/stepSafetyFactor    


    else:
        return 1.0




def getVariableZsteps( fiber:Fiber_class, input_signal:input_signal_class,stepmode,stepSafetyFactor):    
    
    z_so_far=0.0
    z_array=np.array([z_so_far])
    dz_array=np.array([])
    
    
    
    dz_current_step_to_next_step = zstep_NL(0,fiber,input_signal,stepmode,stepSafetyFactor)
    
    
    while (z_so_far+ dz_current_step_to_next_step <= fiber.Length):
        z_so_far+=dz_current_step_to_next_step 
        
        z_array=np.append(z_array,z_so_far)
        dz_array= np.append(dz_array,dz_current_step_to_next_step)
        
        dz_current_step_to_next_step = zstep_NL(z_so_far,fiber,input_signal,stepmode,stepSafetyFactor)
        
    z_array=np.append(z_array,fiber.Length)
    dz_array= np.append(dz_array,fiber.Length-z_so_far)
    
    return (z_array, dz_array)



class ssfm_input_info:
    def __init__(self,input_signal:input_signal_class, fiber:Fiber_class,zinfo,experimentName,directories):
        
        self.experimentName = experimentName
        self.base_dir = directories[0] #Base directory.
        self.current_dir = directories[1] #Directory where output of this experiment is saved.
        
        self.zvals=zinfo[0]
        self.zsteps=zinfo[1]
        
        self.n_z_locs=len(zinfo[0])
        self.n_z_steps=len(zinfo[1])
        
        self.input_signal = input_signal
        self.fiber=fiber
        self.timeFreq=input_signal.timeFreq

class ssfm_output_class:
    def __init__(self, input_signal:input_signal_class, fiber:Fiber_class,zinfo,experimentName,directories):
        
        #Keep input info in separate class so we can save it without wasting several MB on the output pulse and spectrum
        self.input_info=ssfm_input_info(input_signal, fiber,zinfo,experimentName,directories)
        
        self.pulseMatrix = np.zeros((self.input_info.n_z_locs,input_signal.timeFreq.number_of_points ) )*(1+0j)
        self.spectrumMatrix = np.copy(self.pulseMatrix)
        
        self.pulseMatrix[0,:]=np.copy(input_signal.amplitude)   
        self.spectrumMatrix[0,:] = np.copy(input_signal.spectrum)
        
        







def describe_sim_parameters(fiber:Fiber_class,input_signal:input_signal_class,zinfo,experimentName,destination=None):    
     
    if destination != None:
        fig,ax=plt.subplots()
        ax.set_title("Comparison of characteristic lengths") 
    
    
    print(' ### Characteristic parameters of simulation: ###', file = destination)
    print(f'  Length_fiber \t= {fiber.Length/1e3}km', file = destination)
    if fiber.alpha_Np_per_m == 0:
        L_eff = fiber.Length
    else:
        L_eff = (1-np.exp(-fiber.alpha_Np_per_m*fiber.Length))/fiber.alpha_Np_per_m
    print(f"  L_eff \t= {L_eff/1e3:.4f} km", file = destination)
    
    if destination != None:
        ax.barh("Fiber Length", fiber.Length/1e3, color ='C0')
        ax.barh("Effective Length", L_eff/1e3, color ='C1')

    
    
    if fiber.beta2 != 0.0:
        Length_disp = input_signal.duration**2/np.abs(fiber.beta2)
    else:
        Length_disp=np.inf
    print(f"  Length_disp \t= {Length_disp/1e3:.4f}km", file = destination)  
    
    if destination != None:
        ax.barh("Dispersion Length",Length_disp/1e3, color ='C2')
    
    
    if fiber.gamma !=0.0:
        Length_NL = 1/fiber.gamma/input_signal.Pmax   
        N_soliton=np.sqrt(Length_disp/Length_NL)
    else:
        Length_NL=np.inf
        N_soliton=np.NaN
    
    if destination != None:
        ax.barh("Nonlinear Length",Length_NL/1e3, color ='C3')
    
    print(f"  Length_NL \t= {Length_NL/1e3:.4f}km", file = destination)
    print(f"  N_soliton \t= {N_soliton:.4f}", file = destination)
    print(f"  N_soliton^2 \t= {N_soliton**2:.4f}", file = destination)


    if fiber.beta2<0:
        
        z_soliton = pi/2*Length_disp
        
        if destination != None:
            ax.barh("Soliton Length",z_soliton/1e3, color ='C4')
        
        print(' ', file = destination)
        print(f'  sign(beta2) \t= {np.sign(fiber.beta2)}, so Solitons and Modulation Instability may occur ', file = destination)
        print(f"   z_soliton \t= {z_soliton/1e3:.4f}km", file = destination)
        print(f"   N_soliton \t= {N_soliton:.4f}", file = destination)
        print(f"   N_soliton^2 \t= {N_soliton**2:.4f}", file = destination)
        print(" ", file = destination)
        
        # https://prefetch.eu/know/concept/modulational-instability/
        f_MI=np.sqrt(2*fiber.gamma*input_signal.Pmax/np.abs(fiber.beta2))/2/np.pi    
        gain_MI=2*fiber.gamma*input_signal.Pmax
        print(f"   Freq. w. max MI gain = {f_MI/1e9:.4f}GHz", file = destination)
        print(f"   Max MI gain \t\t= {gain_MI*1e3:.4f}/km ", file = destination)
        print(f"   Min MI gain distance = {1/(gain_MI*1e3):.4f}km ", file = destination)
        print(' ', file = destination)
        
        if destination != None:
            ax.barh("MI gain Length",1/(gain_MI*1e3), color ='C5')
        
    elif fiber.beta2>0:           
        #https://prefetch.eu/know/concept/optical-wave-breaking/
        Nmin_OWB = np.sqrt(0.25*np.exp(3/2)) #Minimum N-value of Optical Wave breaking with Gaussian pulse
        Length_wave_break = Length_disp/np.sqrt(N_soliton**2/Nmin_OWB**2-1)  #Characteristic length for Optical Wave breaking with Gaussian pulse
        print(' ', file = destination)
        print(f'  sign(beta2) \t= {np.sign(fiber.beta2)}, so Optical Wave Breaking may occur ', file = destination)
        print(f"   Length_wave_break \t= {Length_wave_break/1e3:.4f} km", file = destination)    
        
        if destination != None:
            ax.barh("OWB Length",Length_wave_break/1e3, color ='C6')
    
    if destination != None:
        ax.barh("Maximum $\Delta$z",np.max(zinfo[1])/1e3, color ='C7')
        ax.barh("Minimum $\Delta$z",np.min(zinfo[1])/1e3, color ='C8')
        
            
        ax.set_xscale('log')
        ax.set_xlabel('Length [km]')
    
    
        plt.savefig('Length_chart.png', 
                    bbox_inches ="tight",
                    pad_inches = 1,
                    orientation ='landscape')
    
        plt.show()
    
    #End of describe_sim_parameters

def getZsteps(fiber:Fiber_class,input_signal:input_signal_class,stepConfig_list,experimentName):
    
    stepMode=stepConfig_list[0]
    stepApproach=stepConfig_list[1]       
    stepSafetyFactor=stepConfig_list[2]
    
    zinfo = (np.array([0,fiber.Length]),fiber.Length)
    


    if stepMode.lower() == "fixed":
        
        if type(stepApproach) == str:
        
            dz=zstep_NL(0,fiber, input_signal,stepApproach,stepSafetyFactor)
            z_array=np.arange(0,fiber.Length,dz)
            
            if z_array[-1] != fiber.Length:
                z_array=np.append(z_array,fiber.Length)
            
            dz_array = np.diff( z_array)
            
            
        elif type(stepApproach) == int:
            z_array=np.linspace(0,fiber.Length,stepApproach+1)
            dz_array=np.ones( stepApproach)*(z_array[1]-z_array[0])            

            
        zinfo   =(z_array,dz_array)
        
        
        
        
    else:
        zinfo = getVariableZsteps(fiber,input_signal,stepApproach,stepSafetyFactor)
        
    fig,ax = plt.subplots()
    ax.set_title(f"Stepmode = ({stepConfig_list[0]},{stepConfig_list[1]}), stepSafetyFactor = {stepConfig_list[2]}")
    ax.plot(zinfo[0]/1e3,'b.',label = f"z-locs ({len(zinfo[0])})")

    ax.set_xlabel('Entry')
    ax.set_ylabel('z-location [km]')
    ax.tick_params(axis='y',labelcolor='b')
    
    ax2=ax.twinx()
    ax2.plot(zinfo[1]/1e3,'r.',label = f"$\Delta$z-steps ({len(zinfo[1])})")
    ax2.set_ylabel('$\Delta$z [km]')
    ax2.tick_params(axis='y',labelcolor='r')
    
    fig.legend(bbox_to_anchor=(1.3,0.8))
    
    plt.savefig('Z-step_chart.png', 
                bbox_inches ="tight",
                pad_inches = 1,
                orientation ='landscape')
    plt.show()
    
    
    
    return zinfo
      

def describe_run( current_time, current_fiber:Fiber_class,  current_input_signal:input_signal_class,current_stepConfig, zinfo,experimentName  ,destination = None):

    print('Time when run was started:', file = destination)
    print(current_time,file=destination)
    print(' ', file = destination)

    
    
    print('Info about time basis:', file = destination)
    current_input_signal.timeFreq.describe_config(destination = destination)

    
    print('Info about input signal:', file = destination)
    current_input_signal.describe_input_signal(destination=destination)


    print(' ', file = destination)
    
    describe_sim_parameters(current_fiber,current_input_signal,zinfo,experimentName,destination=destination)
    
    
    print(' ', file = destination)
    print(f"Stepmode = ({current_stepConfig[0]},{current_stepConfig[1]}), stepSafetyFactor = {current_stepConfig[2]}", file = destination)
    print(' ', file = destination)
    
    

def SSFM(fiber:Fiber_class,input_signal:input_signal_class,stepConfig=("fixed","cautious",10.0),experimentName ="most_recent_run"):
    
    base_dir=os.getcwd()+'\\'
    os.chdir(base_dir)
    

    current_dir = "Simulation Results\\most_recent_run\\"
    current_time = datetime.now()
    
    if experimentName == "most_recent_run":
        current_dir = "Simulation Results\\most_recent_run\\"
        overwrite_folder_flag = True  
    else:
        
        current_dir =base_dir+ f"Simulation Results\\{experimentName}\\{current_time.year}_{current_time.month}_{current_time.day}_{current_time.hour}_{current_time.minute}_{current_time.second}\\"
        overwrite_folder_flag = False 
        
    os.makedirs(current_dir,exist_ok=overwrite_folder_flag)
    os.chdir(current_dir)
    
    dirs = (base_dir,current_dir)
    print("########### Initializing SSFM!!! ###########")
    
    
    zinfo = getZsteps(fiber,input_signal,stepConfig,experimentName)
    

    

    #Initialize arrays to store pulse and spectrum throughout fiber
    ssfm_result = ssfm_output_class(input_signal,fiber,zinfo,experimentName,dirs)

    
    print("Saving SSFM input to current folder using the 'pickle' library")
    
    with open("ssfm_input.pickle", "wb") as file:
        pickle.dump(ssfm_result.input_info,file)    

    with open("input_config_description.txt","w") as output_file:
            #Print info to terminal
            describe_run( current_time, fiber,  input_signal,stepConfig, zinfo,experimentName)
            
            #Print info to file
            describe_run( current_time, fiber,  input_signal,stepConfig, zinfo,experimentName  ,destination = output_file)

    
    
    print(f"Running SSFM with nsteps = {len(zinfo[1])}")
    
   
    #Pre-calculate effect of dispersion and loss as it's the same everywhere
    disp_and_loss=np.exp((1j*fiber.beta2/2*(2*pi*input_signal.timeFreq.f)**2-fiber.alpha_Np_per_m/2))
    
    #Precalculate constants for nonlinearity
    nonlinearity=1j*fiber.gamma
    
    #Initialize arrays to store temporal profile and spectrum while calculating SSFM
    pulse    = np.copy(input_signal.amplitude )
    spectrum = np.copy(input_signal.spectrum )
    
    
    for n, dz in enumerate(zinfo[1]):   
        pulse*=np.exp(nonlinearity*getPower(pulse)*dz) #Apply nonlinearity
        
        spectrum = getSpectrumFromPulse(input_signal.timeFreq.t, pulse)*(disp_and_loss**dz) #Go to spectral domain and apply disp and loss
        
        
        pulse=getPulseFromSpectrum(input_signal.timeFreq.f, spectrum) #Return to time domain 
        
        
        #Store results and repeat
        ssfm_result.pulseMatrix[n+1,:]=pulse
        ssfm_result.spectrumMatrix[n+1,:]=spectrum

    #Return results
    print("Finished running SSFM!!!")
    

    
    os.chdir(ssfm_result.input_info.base_dir)
    
    
    return ssfm_result




#Function for optionally saving plots
def saveplot(basename):

    
    if basename.lower().endswith(('.pdf','.png','.jpg')) == False:
        basename+='.png'
        
    plt.savefig(basename, bbox_inches='tight', pad_inches=0)


#Function for optionally deleting plots     

def removePlots(filetypes):
  dir_name = os.getcwd()
  filelist = os.listdir(dir_name)
  for item in filelist:
    
    for filetype in filetypes:
      if isdir(item):
        continue

      if item.endswith(filetype):
          print("Removed:"+item)
          os.remove(item)
          
def plotFirstAndLastPulse(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff,**kwargs):
  
    sim = ssfm_result.input_info.timeFreq
    zvals=ssfm_result.input_info.zvals
    matrix = ssfm_result.pulseMatrix 

    t=sim.t[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]*1e12

    P_initial=getPower(matrix[0,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)])
    P_final=getPower(matrix[-1,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)])


    Pmax_initial = np.max(P_initial)
    Pmax_final = np.max(P_final)
    Pmax=np.max([Pmax_initial,Pmax_final])

    fig, ax = plt.subplots(dpi=300)
    ax.set_title("Initial pulse and final pulse")
    ax.plot(t,P_initial,label="Initial Pulse at z = 0")
    ax.plot(t,P_final,label=f"Final Pulse at z = {zvals[-1]/1e3}km")
    
    ax.set_xlabel("Time [ps]")
    ax.set_ylabel("Power [W]")
    ax.set_ylim(Pmax/(10**(-dB_cutoff/10)),1.05*Pmax)
    #plt.xlim(-2.5*ssfm_result.input_signal.duration*1e12,2.5*ssfm_result.input_signal.duration*1e12)
    #plt.yscale('log')

    ax.legend(bbox_to_anchor=(1.05,0.8))
    saveplot('first_and_last_pulse',**kwargs)
    plt.show()  


def plotPulseMatrix2D(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff,**kwargs):
    sim = ssfm_result.input_info.timeFreq
    zvals=ssfm_result.input_info.zvals
    matrix = ssfm_result.pulseMatrix 

    #Plot pulse evolution throughout fiber in normalized log scale
    fig, ax = plt.subplots()
    ax.set_title('Pulse Evolution (dB scale)')
    t = sim.t[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]*1e12
    z = zvals
    T, Z = np.meshgrid(t, z)
    P=getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]  )/np.max(getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]))
    P[P<1e-100]=1e-100
    P = 10*np.log10(P)
    P[P<dB_cutoff]=dB_cutoff
    surf=ax.contourf(T, Z, P,levels=40, cmap="jet")
    ax.set_xlabel('Time [ps]')
    ax.set_ylabel('Distance [m]')
    cbar=fig.colorbar(surf, ax=ax)
    saveplot('pulse_evo_2D',**kwargs) 
    plt.show()

def plotPulseMatrix3D(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff,**kwargs):
    sim = ssfm_result.input_info.timeFreq
    zvals=ssfm_result.input_info.zvals
    matrix = ssfm_result.pulseMatrix 
  
    #Plot pulse evolution in 3D
    fig, ax = plt.subplots(1,1, figsize=(10,7),subplot_kw={"projection": "3d"})
    plt.title("Pulse Evolution (dB scale)")

    t = sim.t[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]*1e12
    z = zvals
    T_surf, Z_surf = np.meshgrid(t, z)
    P_surf=getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]  )/np.max(getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]))
    P_surf[P_surf<1e-100]=1e-100
    P_surf = 10*np.log10(P_surf)
    P_surf[P_surf<dB_cutoff]=dB_cutoff
    # Plot the surface.
    surf = ax.plot_surface(T_surf, Z_surf, P_surf, cmap=cm.jet,
                            linewidth=0, antialiased=False)
    ax.set_xlabel('Time [ps]')
    ax.set_ylabel('Distance [m]')
    # Add a color bar which maps values to colors.
    fig.colorbar(surf, shrink=0.5, aspect=5)
    saveplot('pulse_evo_3D',**kwargs)
    plt.show()


def plotPulseChirp2D(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff,**kwargs):
    
    sim = ssfm_result.input_info.timeFreq
    zvals=ssfm_result.input_info.zvals
    matrix = ssfm_result.pulseMatrix   

    #Plot pulse evolution throughout fiber  in normalized log scale
    fig, ax = plt.subplots()
    ax.set_title('Pulse Chirp Evolution')
    t = sim.t[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]*1e12
    z = zvals
    T, Z = np.meshgrid(t, z)
    
    
    Cmatrix=np.ones( (len(z),len(t))  )*1.0

    for i in range(len(zvals)):
        Cmatrix[i,:]=getChirp(t/1e12,matrix[i,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)])/1e9


    for kw, value in kwargs.items():
        if kw.lower()=='chirpplotrange' and type(value)==tuple:
            Cmatrix[Cmatrix<value[0]]=value[0]
            Cmatrix[Cmatrix>value[1]]=value[1]


    surf=ax.contourf(T, Z, Cmatrix,levels=40,cmap='RdBu')
    
    ax.set_xlabel('Time [ps]')
    ax.set_ylabel('Distance [m]')
    cbar=fig.colorbar(surf, ax=ax)
    cbar.set_label('Chirp [GHz]')
    saveplot('chirp_evo_2D') 
    plt.show()


def plotEverythingAboutPulses(ssfm_result:ssfm_output_class, 
                              nrange:int, 
                              dB_cutoff, **kwargs):
  

    
    
    os.chdir(ssfm_result.input_info.current_dir)


    print('  ')
    plotFirstAndLastPulse(ssfm_result, nrange, dB_cutoff)
    plotPulseMatrix2D(ssfm_result,nrange,dB_cutoff)
    plotPulseChirp2D(ssfm_result,nrange,dB_cutoff,**kwargs) 
    plotPulseMatrix3D(ssfm_result,nrange,dB_cutoff)
    print('  ')

    
    os.chdir(ssfm_result.input_info.base_dir)
        


def plotFirstAndLastSpectrum(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff):

    matrix = ssfm_result.spectrumMatrix
    sim = ssfm_result.input_info.timeFreq
    
    P_initial=getPower(matrix[0,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)])*1e9
    P_final=getPower(matrix[-1,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)])*1e9
    
    
    Pmax_initial = np.max(P_initial)
    Pmax_final = np.max(P_final)
    Pmax=np.max([Pmax_initial,Pmax_final]) 

    f=sim.f[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]/1e9
    plt.figure()
    plt.title("Initial spectrum and final spectrum")
    plt.plot(f,P_initial,label="Initial Spectrum")
    plt.plot(f,P_final,label="Final Spectrum")
    plt.xlabel("Freq. [GHz]")
    plt.ylabel("PSD [W/GHz]")
    plt.yscale('log')
    plt.ylim(Pmax/(10**(-dB_cutoff/10)),1.05*Pmax)
    plt.legend()
    saveplot('first_and_last_spectrum')
    plt.show()

def plotSpectrumMatrix2D(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff):
    
    matrix = ssfm_result.spectrumMatrix
    sim = ssfm_result.input_info.timeFreq
    zvals = ssfm_result.input_info.zvals
    
    
    #Plot pulse evolution throughout fiber in normalized log scale
    fig, ax = plt.subplots()
    ax.set_title('Spectrum Evolution (dB scale)')
    f = sim.f[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]/1e9 
    z = zvals
    F, Z = np.meshgrid(f, z)
    Pf=getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]  )/np.max(getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]))
    Pf[Pf<1e-100]=1e-100
    Pf = 10*np.log10(Pf)
    Pf[Pf<dB_cutoff]=dB_cutoff
    surf=ax.contourf(F, Z, Pf,levels=40)
    ax.set_xlabel('Freq. [GHz]')
    ax.set_ylabel('Distance [m]')
    cbar=fig.colorbar(surf, ax=ax) 
    saveplot('spectrum_evo_2D') 
    plt.show()

def plotSpectrumMatrix3D(ssfm_result:ssfm_output_class, nrange:int, dB_cutoff):
    matrix = ssfm_result.spectrumMatrix
    sim = ssfm_result.input_info.timeFreq
    zvals = ssfm_result.input_info.zvals
    
    #Plot pulse evolution in 3D
    fig, ax = plt.subplots(1,1, figsize=(10,7),subplot_kw={"projection": "3d"})
    plt.title("Spectrum Evolution (dB scale)")
      
    f = sim.f[int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]/1e9 
    z = zvals
    F_surf, Z_surf = np.meshgrid(f, z)
    P_surf=getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]  )/np.max(getPower(matrix[:,int(sim.number_of_points/2-nrange):int(sim.number_of_points/2+nrange)]))
    P_surf[P_surf<1e-100]=1e-100
    P_surf = 10*np.log10(P_surf)
    P_surf[P_surf<dB_cutoff]=dB_cutoff
    # Plot the surface.
    surf = ax.plot_surface(F_surf, Z_surf, P_surf, cmap=cm.viridis,
                          linewidth=0, antialiased=False)
    ax.set_xlabel('Freq. [GHz]')
    ax.set_ylabel('Distance [m]')
    # Add a color bar which maps values to colors.
    fig.colorbar(surf, shrink=0.5, aspect=5)
    saveplot('spectrum_evo_3D') 
    plt.show()


def plotEverythingAboutSpectra(ssfm_result:ssfm_output_class,
                               nrange:int, 
                               dB_cutoff,
                               **kwargs):
  
    os.chdir(ssfm_result.input_info.current_dir)
        
    print('  ')  
    plotFirstAndLastSpectrum(ssfm_result, nrange, dB_cutoff)
    plotSpectrumMatrix2D(ssfm_result, nrange, dB_cutoff)
    plotSpectrumMatrix3D(ssfm_result, nrange, dB_cutoff)
    print('  ')  

    os.chdir(ssfm_result.input_info.base_dir)



if __name__ == "__main__":
    
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    
    
    N  = 2**15 #Number of points
    dt = 0.05e-12 #Time resolution [s] 
    
    
    timeFreq_test=timeFreq_class(N,dt)
    
    #Define fiberulation parameters
    Length          = 500      #Fiber length in m
    #nsteps          = 2**8     #Number of steps we divide the fiber into
    
    gamma           = 40e-3     #Nonlinearity parameter in 1/W/m 
    beta2           = 100e3    #Dispersion in fs^2/m (units typically used when referring to beta2) 
    beta2          *= (1e-30)  #Convert fs^2 to s^2 so everything is in SI units
    alpha_dB_per_m  = 10.0e-3   #Power attenuation coeff in decibel per m. Usual value at 1550nm is 0.2 dB/km
    
    #Note:  beta2>0 is normal dispersion with red light pulling ahead, 
    #       causing a negative leading chirp
    #       
    #       beta2<0 is anormalous dispersion with blue light pulling ahead, 
    #       causing a positive leading chirp.
    
      
    #  Initialize class
    fiber=Fiber_class(Length, gamma, beta2, alpha_dB_per_m)
    
    
    #Initialize Gaussian pulse

    
    testAmplitude = np.sqrt(1)                    #Amplitude in units of sqrt(W)
    testDuration  =1000*timeFreq_test.time_step   #Pulse 1/e^2 duration [s]
    testOffset    = 0                       #Time offset
    testChirp = 0
    testCarrierFreq=0
    testPulseType='gaussian' 
    testOrder = 1
    testNoiseAmplitude = 1e-3
    

    testInputSignal = input_signal_class(timeFreq_test, 
                                         testAmplitude ,
                                         testDuration,
                                         testOffset,
                                         testChirp,
                                         testCarrierFreq,
                                         testPulseType,
                                         testOrder,
                                         testNoiseAmplitude)
    
    
    if testPulseType.lower() == "custom":
        
        testInputSignal.amplitude +=  getPulse(testInputSignal.timeFreq.t,testAmplitude/100,testDuration*5,0,0,-0.5e9,"square")
        testInputSignal.amplitude +=  getPulse(testInputSignal.timeFreq.t,testAmplitude,testDuration/5,0  ,0,0.5e9,"gaussian")
        testInputSignal.Pmax=np.max(getPower(testInputSignal.amplitude))
        testInputSignal.duration=testDuration/5
        
        testInputSignal.spectrum=getSpectrumFromPulse(testInputSignal.timeFreq.t, testInputSignal.amplitude)
    
    
    testSafetyFactor = 1
    testStepConfig=("fixed",2**8,testSafetyFactor)
    #testStepConfig=("fixed",2**10,testSafetyFactor)
    
    testName="test2"
    #Run SSFM
    ssfm_result_test = SSFM(fiber,testInputSignal,stepConfig=testStepConfig)
    
    #Plot pulses
    nrange_test=600
    cutoff_test=-30
    plotEverythingAboutPulses(ssfm_result_test,nrange_test,cutoff_test,chirpPlotRange=(-60,60))
    
 
    nrange_test=400
    cutoff_test=-60    
    
    #Plot spectra
    plotEverythingAboutSpectra(ssfm_result_test,nrange_test,cutoff_test)


