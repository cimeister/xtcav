#(c) Coded by Alvaro Sanchez-Gonzalez 2014
#Functions related with the XTCAV pulse retrieval
import numpy as np
#
import scipy.interpolate
#import scipy.stats.mstats 

import warnings
import scipy.ndimage as im 
import scipy.io
import math
import cv2
import Constants

from Metrics import *


def ProcessXTCAVImage(image,ROI):
    """
    Obtain the statistics (profiles, center of mass, etc) of an xtcav image. 
    Arguments:
        image: 3d numpy array where the first index always has one dimension (it will become the bunch index), the second index correspond to y, and the third index corresponds to x
        ROI: region of interest of the image, contain x and y axis
    Output:
        imageStats: list with the image statistics for each bunch in the image
    """
    #obtain the number of bunches for the image. In principle this should be equal to n    
    nb=image.shape[0]
    #For the image for each bunch we retrieve the statistics and add them to the list    
    imageStats=[]    
    for i in range(nb):
        imageStats.append(GetImageStatistics(image[i,:,:],ROI.x,ROI.y))
        
    return imageStats
    

def GetCenterOfMass(image,x,y):
    """
    Gets the center of mass of an image 
    Arguments:
      image: 2d numpy array where the firs index correspond to y, and the second index corresponds to x
      x,y: vectors of the image
    Output:
      x0,y0 coordinates of the center of mass 
    """
    profilex=np.sum(image,0);     
    x0=np.dot(profilex,np.transpose(x))/np.sum(profilex)
    profiley=np.sum(image,1);     
    y0=np.dot(profiley,y)/np.sum(profiley)
    
    return x0,y0
    
    
def SubtractBackground(image, ROI, dark_background):
    """
    Obtain all the statistics (profiles, center of mass, etc) of an image
    Arguments:
      image: 2d numpy array where the first index correspond to y, and the second index corresponds to x
      ROI: region of interest of the input image
      darkbg: struct with the dark background image and its ROI
    Output
      image: image after subtracting the background
      ROI: region of interest of the ouput image
    """

    #This only contemplates the case when the ROI of the darkbackground is larger than the ROI of the image. Other cases should be contemplated in the future
    if dark_background:
        image_db = dark_background.image
        ROI_db = dark_background.ROI
        minX = ROI.x0 - ROI_db.x0
        maxX=(ROI.x0+ROI.xN-1)-ROI_db.x0
        minY=ROI.y0-ROI_db.y0
        maxY=(ROI.y0+ROI.yN-1)-ROI_db.y0    
        image=image-image_db[minY:(maxY+1),minX:(maxX+1)]
       
    return image,ROI

    
def DenoiseImage(image,medianfilter,snrfilter):
    """
    Get rid of some of the noise in the image (profiles, center of mass, etc) of an image
    Arguments:
      image: 2d numpy array where the first index correspond to y, and the second index corresponds to x
      medianfilter: number of neighbours for the median filter
      snrfilter: factor to multiply the standard deviation of the noise to use as a threshold
    Output
      image: filtered image
      ok: true if there is something in the image
    """
    contains_data=True
    #Applygin the median filter
    image=im.median_filter(image,medianfilter)
    
    #Obtaining the mean and the standard deviation of the noise
    mean=np.mean(image[0:Constants.SNR_BORDER,0:Constants.SNR_BORDER]);
    std=np.std(image[0:Constants.SNR_BORDER,0:Constants.SNR_BORDER]);
    
    if(np.sum(image)<=0):
        print np.sum(image)
        warnings.warn_explicit('Image Completely Empty After Background Subtraction',UserWarning,'XTCAV',0)
        contains_data=0
    
    #Subtracting the mean of the noise
    image=image-mean
    
    #Setting a threshold equal to signal to noise ratio times the standard deviation
    thres=snrfilter*std    
    image[image < thres] = 0 
    ### look at standard deviation instead
    #We also normalize the image to have a total area of one
    # if(np.sum(image)>0):
    #     if (np.sort(image.flatten())[-100]<200):#We make sure it is not just noise, but looking at the 200th pixel
    #         warnings.warn_explicit('Image Completely Empty',UserWarning,'XTCAV',0)
    #         ok=0
    image=image/np.sum(image)
    # else:
    #     warnings.warn_explicit('Image Completely Empty',UserWarning,'XTCAV',0)
    #     ok=0        
    
    return image, contains_data

def FindROI(image,ROI,threshold,expandfactor):
    """
    Find the subroi of the image
    Arguments:
      image: 2d numpy array where the first index correspond to y, and the second index corresponds to x
      ROI: region of interest of the input image
      threshold: fraction of one that will set where the signal has dropped enough from the maximum to consider it to be the width the of trace
      expandfactor: factor that will increase the calculated width from the maximum to where the signal drops to threshold
    Output
      cropped: 2d numpy array with the cropped image where the first index correspond to y, and the second index corresponds to x
      outROI: region of interest of the output image
    """

    #For the cropping on each direction we use the profile on each direction
    profileX=image.sum(0)
    profileY=image.sum(1)
    
    maxpos=np.argmax(profileX);                             #Position of the maximum
    thres=profileX[maxpos]*threshold;                       #Threshold value
    overthreshold=np.nonzero(profileX>=thres)[0];           #Indices that correspond to values higher than the threshold
    center=(overthreshold[0]+overthreshold[-1])/2;          #Middle position between the first value and the last value higher than th threshold
    width=(overthreshold[-1]-overthreshold[0]+1)*expandfactor;  #Total width after applying the expand factor
    ind1X=np.round(center-width/2).astype(np.int)                         #Index on the left side form the center
    ind2X=np.round(center+width/2).astype(np.int)                         #Index on the right side form the center
    ind1X=np.amax([0,ind1X]).astype(np.int)                                #Check that the index is not too negative
    ind2X=np.amin([profileX.size,ind2X]).astype(np.int)                    #Check that the index is not too high
    
    #Same for y
    maxpos=np.argmax(profileY);
    thres=profileY[maxpos]*threshold;
    overthreshold=np.nonzero(profileY>=thres)[0];
    center=(overthreshold[0]+overthreshold[-1])/2;
    width=(overthreshold[-1]-overthreshold[0]+1)*expandfactor;
    ind1Y = np.round(center-width/2).astype(np.int)
    ind2Y = np.round(center+width/2).astype(np.int)
    ind1Y = np.amax([0,ind1Y]).astype(np.int)
    ind2Y = np.amin([profileY.size,ind2Y]).astype(np.int)
   
    #Cropping the image using the calculated indices
    cropped=np.zeros((ind2Y-ind1Y,ind2X-ind1X))
    cropped[:,:]=image[ind1Y:ind2Y,ind1X:ind2X]
                
    #Output ROI in terms of the input ROI            
    outROI = ROIMetrics(ind2X-ind1X+1, 
        ROI.x0+ind1X, 
        ind2Y-ind1Y+1, 
        ROI.y0+ind1Y, 
        x=ROI.x0+np.arange(ind1X, ind2X), 
        y=ROI.y0+np.arange(ind1Y, ind2Y))
    
    return cropped,outROI


def GetImageStatistics(image, x, y):
    imFrac=np.sum(image)    #Total area of the image: Since the original image is normalized, this should be on for on bunch retrievals, and less than one for multiple bunches
    xProfile=np.sum(image,0)  #Profile projected onto the x axis
    yProfile=np.sum(image,1)  #Profile projected onto the y axis
    
    xCOM=np.dot(xProfile,np.transpose(x))/imFrac        #X position of the center of mass
    xRMS= np.sqrt(np.dot((x-xCOM)**2,xProfile)/imFrac); #Standard deviation of the values in x
    ind=np.where(xProfile >= np.amax(xProfile)/2)[0];   
    xFWHM=np.abs(ind[-1]-ind[0]+1);                     #FWHM of the X profile

    yCOM=np.dot(yProfile,y)/imFrac                      #Y position of the center of mass
    yRMS= np.sqrt(np.dot((y-yCOM)**2,yProfile)/imFrac); #Standard deviation of the values in y
    ind=np.where(yProfile >= np.amax(yProfile)/2);
    yFWHM=np.abs(ind[-1]-ind[0])                        #FWHM of the Y profile
    
    yCOMslice=divideNoWarn(np.dot(np.transpose(image),y),xProfile,yCOM);   #Y position of the center of mass for each slice in x
    distances=np.outer(np.ones(yCOMslice.shape[0]),y)-np.outer(yCOMslice,np.ones(image.shape[0]))    #For each point of the image, the distance to the y center of mass of the corresponding slice
    yRMSslice= divideNoWarn(np.sum(np.transpose(image)*((distances)**2),1),xProfile,0)         #Width of the distribution of the points for each slice around the y center of masses                  
    yRMSslice = np.sqrt(yRMSslice)
    
    if imFrac==0:   #What to to if the image was effectively full of zeros
        xCOM=float(x[-1]+x[0])/2
        xRMS=0
        xFWHM=0
        yCOM=float(y[-1]+y[0])/2
        yRMS=0
        yFWHM=0
        yCOMslice[np.isnan(yCOMslice)]=yCOM

    return ImageStatistics(imFrac, xProfile, yProfile, xCOM,
        yCOM, xRMS, yRMS, xFWHM, yFWHM, yCOMslice, yRMSslice)


def CalculatePhyscialUnits(ROI, center, shot_to_shot, global_calibration):
    valid=1
    yMeVPerPix = global_calibration.umperpix*global_calibration.dumpe/global_calibration.dumpdisp*1e-3          #Spacing of the y axis in MeV
    
    xfsPerPix = -global_calibration.umperpix*global_calibration.rfampcalib/(0.3*global_calibration.strstrength*shot_to_shot.xtcavrfamp)     #Spacing of the x axis in fs (this can be negative)
    
    cosphasediff=math.cos((global_calibration.rfphasecalib-shot_to_shot.xtcavrfphase)*math.pi/180)

    #If the cosine of phase was too close to 0, we return warning and error
    if np.abs(cosphasediff)<0.5:
        warnings.warn_explicit('The phase of the bunch with the RF field is far from 0 or 180 degrees',UserWarning,'XTCAV',0)
        valid=0

    signflip = np.sign(cosphasediff); #It may need to be flipped depending on the phase

    xfsPerPix = signflip*xfsPerPix;    
    
    xfs=xfsPerPix*(ROI.x-center[0])                  #x axis in fs around the center of mass
    yMeV=yMeVPerPix*(ROI.y-center[1])                #y axis in MeV around the center of mass

    return PhysicalUnits(xfs, yMeV, xfsPerPix, yMeVPerPix, valid)


def ProcessLasingSingleShot(image_profile, nolasingAveragedProfiles):
    """
    Process a single shot profiles, using the no lasing references to retrieve the x-ray pulse(s)
    Arguments:
      image_profile: profile for xtcav image
      nolasingAveragedProfiles: no lasing reference profiles
    Output
      pulsecharacterization: retrieved pulse
    """

    image_stats = image_profile.image_stats
    physical_units = image_profile.physical_units
    shot_to_shot = image_profile.shot_to_shot

    num_bunches = len(image_stats)              #Number of bunches
    
    if (num_bunches != nolasingAveragedProfiles.num_bunches):
        warnings.warn_explicit('Different number of bunches in the reference',UserWarning,'XTCAV',0)
    
    t = nolasingAveragedProfiles.t   #Master time obtained from the no lasing references
    dt = (t[-1]-t[0])/(t.size-1)
    
             #Electron charge in coulombs
    Nelectrons = shot_to_shot.dumpecharge/Constants.E_CHARGE   #Total number of electrons in the bunch    
    
    #Create the the arrays for the outputs, first index is always bunch number
    bunchdelay=np.zeros(num_bunches, dtype=np.float64);                       #Delay from each bunch with respect to the first one in fs
    bunchdelaychange=np.zeros(num_bunches, dtype=np.float64);                 #Difference between the delay from each bunch with respect to the first one in fs and the same form the non lasing reference
    bunchenergydiff=np.zeros(num_bunches, dtype=np.float64);                  #Distance in energy for each bunch with respect to the first one in MeV
    bunchenergydiffchange=np.zeros(num_bunches, dtype=np.float64);            #Comparison of that distance with respect to the no lasing
    eBunchCOM=np.zeros(num_bunches, dtype=np.float64);                   #Energy of the XRays generated from each bunch for the center of mass approach in J
    eBunchRMS=np.zeros(num_bunches, dtype=np.float64);                   #Energy of the XRays generated from each bunch for the dispersion of mass approach in J
    powerAgreement=np.zeros(num_bunches, dtype=np.float64);              #Agreement factor between the two methods
    lasingECurrent=np.zeros((num_bunches,t.size), dtype=np.float64);     #Electron current for the lasing trace (In #electrons/s)
    nolasingECurrent=np.zeros((num_bunches,t.size), dtype=np.float64);   #Electron current for the no lasing trace (In #electrons/s)
    lasingECOM=np.zeros((num_bunches,t.size), dtype=np.float64);         #Lasing energy center of masses for each time in MeV
    nolasingECOM=np.zeros((num_bunches,t.size), dtype=np.float64);       #No lasing energy center of masses for each time in MeV
    lasingERMS=np.zeros((num_bunches,t.size), dtype=np.float64);         #Lasing energy dispersion for each time in MeV
    nolasingERMS=np.zeros((num_bunches,t.size), dtype=np.float64);       #No lasing energy dispersion for each time in MeV
    powerECOM=np.zeros((num_bunches,t.size), dtype=np.float64);      #Retrieved power in GW based on ECOM
    powerERMS=np.zeros((num_bunches,t.size), dtype=np.float64);      #Retrieved power in GW based on ERMS

    powerrawECOM=np.zeros((num_bunches,t.size), dtype=np.float64);              #Retrieved power in GW based on ECOM without gas detector normalization
    powerrawERMS=np.zeros((num_bunches,t.size), dtype=np.float64);              #Retrieved power in arbitrary units based on ERMS without gas detector normalization
    groupnum=np.zeros(num_bunches, dtype=np.int32);                  #group number of lasing off shot
             
    
    #We treat each bunch separately
    for j in range(num_bunches):
        distT=(image_stats[j].xCOM-image_stats[0].xCOM)*physical_units.xfsPerPix  #Distance in time converted form pixels to fs
        distE=(image_stats[j].yCOM-image_stats[0].yCOM)*physical_units.yMeVPerPix #Distance in time converted form pixels to MeV
        
        bunchdelay[j]=distT  #The delay for each bunch is the distance in time
        bunchenergydiff[j]=distE #Same for energy
        
        dt_old=physical_units.xfs[1]-physical_units.xfs[0] # dt before interpolation 
        
        eCurrent=image_stats[j].xProfile/(dt_old*1e-15)*Nelectrons                        #Electron current in number of electrons per second, the original xProfile already was normalized to have a total sum of one for the all the bunches together
        
        eCOMslice=(image_stats[j].yCOMslice-image_stats[j].yCOM)*physical_units.yMeVPerPix       #Center of mass in energy for each t converted to the right units        
        eRMSslice=image_stats[j].yRMSslice*physical_units.yMeVPerPix                               #Energy dispersion for each t converted to the right units

        interp=scipy.interpolate.interp1d(physical_units.xfs-distT,eCurrent,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True)  #Interpolation to master time
        eCurrent=interp(t);    
                                                   
        interp=scipy.interpolate.interp1d(physical_units.xfs-distT,eCOMslice,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True)  #Interpolation to master time
        eCOMslice=interp(t);
            
        interp=scipy.interpolate.interp1d(physical_units.xfs-distT,eRMSslice,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True)  #Interpolation to master time
        eRMSslice=interp(t)        
        
        #Find best no lasing match
        NG=nolasingAveragedProfiles.eCurrent.shape[1];
        err= np.zeros(NG, dtype=np.float64);
        for g in range(NG):
            err[g] = np.corrcoef(eCurrent,nolasingAveragedProfiles.eCurrent[j,g,:])[0,1]**2;
        
        #The index of the most similar is that with a highest correlation, i.e. the last in the array after sorting it
        order=np.argsort(err)
        refInd=order[-1];
        groupnum[j]=refInd
        
        #The change in the delay and in energy with respect to the same bunch for the no lasing reference
        bunchdelaychange[j]=distT-nolasingAveragedProfiles.distT[j,refInd]
        bunchenergydiffchange[j]=distE-nolasingAveragedProfiles.distE[j,refInd]
                                       
        #We do proper assignations
        lasingECurrent[j,:]=eCurrent
        nolasingECurrent[j,:]=nolasingAveragedProfiles.eCurrent[j,refInd,:]

        
        #We threshold the ECOM and ERMS based on electron current
        threslevel=0.1;
        threslasing=np.amax(lasingECurrent[j,:])*threslevel;
        thresnolasing=np.amax(nolasingECurrent[j,:])*threslevel;       
        indiceslasing=np.where(lasingECurrent[j,:]>threslasing)
        indicesnolasing=np.where(nolasingECurrent[j,:]>thresnolasing)      
        ind1=np.amax([indiceslasing[0][0],indicesnolasing[0][0]])
        ind2=np.amin([indiceslasing[0][-1],indicesnolasing[0][-1]])        
        if ind1>ind2:
            ind1=ind2
            
        
        #And do the rest of the assignations taking into account the thresholding
        lasingECOM[j,ind1:ind2]=eCOMslice[ind1:ind2]
        nolasingECOM[j,ind1:ind2]=nolasingAveragedProfiles.eCOMslice[j,refInd,ind1:ind2]
        lasingERMS[j,ind1:ind2]=eRMSslice[ind1:ind2]
        nolasingERMS[j,ind1:ind2]=nolasingAveragedProfiles.eRMSslice[j,refInd,ind1:ind2]
        
        
        #First calculation of the power based on center of masses and dispersion for each bunch
        powerECOM[j,:]=((nolasingECOM[j,:]-lasingECOM[j,:])*Constants.E_CHARGE*1e6)*eCurrent    #In J/s
        powerERMS[j,:]=(lasingERMS[j,:]**2-nolasingERMS[j,:]**2)*(eCurrent**(2.0/3.0)) #
        
    powerrawECOM=powerECOM*1e-9 
    powerrawERMS=powerERMS.copy()
    #Calculate the normalization constants to have a total energy compatible with the energy detected in the gas detector
    eoffsetfactor=(shot_to_shot.xrayenergy-(np.sum(powerECOM)*dt*1e-15))/Nelectrons   #In J                           
    escalefactor=np.sum(powerERMS)*dt*1e-15                 #in J
    
    
    #Apply the corrections to each bunch and calculate the final energy distribution and power agreement
    for j in range(num_bunches):                 
        powerECOM[j,:]=((nolasingECOM[j,:]-lasingECOM[j,:])*Constants.E_CHARGE*1e6+eoffsetfactor)*lasingECurrent[j,:]*1e-9   #In GJ/s (GW)
        powerERMS[j,:]=shot_to_shot.xrayenergy*powerERMS[j,:]/escalefactor*1e-9   #In GJ/s (GW)        
        powerAgreement[j]=1-np.sum((powerECOM[j,:]-powerERMS[j,:])**2)/(np.sum((powerECOM[j,:]-np.mean(powerECOM[j,:]))**2)+np.sum((powerERMS[j,:]-np.mean(powerERMS[j,:]))**2))
        eBunchCOM[j]=np.sum(powerECOM[j,:])*dt*1e-15*1e9
        eBunchRMS[j]=np.sum(powerERMS[j,:])*dt*1e-15*1e9
                    
    return PulseCharacterization(t, powerrawECOM, powerrawERMS, powerECOM, 
        powerERMS, powerAgreement, bunchdelay, bunchdelaychange, shot_to_shot.xrayenergy, 
        eBunchCOM, eBunchRMS, bunchenergydiff, bunchenergydiffchange, lasingECurrent,
        nolasingECurrent, lasingECOM, nolasingECOM, lasingERMS, nolasingERMS, num_bunches, 
        groupnum)
    
def AverageXTCAVProfilesGroups(list_image_profiles, shots_per_group):
    """
    Find the subroi of the image
    Arguments:
      list_image_profiles: list of the image profiles for all the XTCAV non lasing profiles to average
      shots_per_group
    Output
      averagedProfiles: list with the averaged reference of the reference for each group 
    """
   
    list_image_stats = [profile.image_stats for profile in list_image_profiles]
    list_physical_units = [profile.physical_units for profile in list_image_profiles]
    list_roi = [profile.roi for profile in list_image_profiles]
    list_shot_to_shot = [profile.shot_to_shot for profile in list_image_profiles]

    num_profiles = len(list_image_profiles)           #Total number of profiles
    num_bunches = len(list_image_stats[0])       #Number of bunches
    num_groups = int(np.floor(num_profiles/shots_per_group))   #Number of groups to make
            
    
    # Obtain physical units and calculate time vector   
    maxt=0          #Set an initial maximum, minimum and increment value for the master time vector
    mint=0
    mindt=1000

    #We find adequate values for the master time
    for i in range(num_profiles):
        #We compare and update the maximum, minimum and increment value for the master time vector
        maxt=np.amax([maxt,np.amax(list_physical_units[i].xfs)])
        mint=np.amin([mint,np.amin(list_physical_units[i].xfs)])
        mindt=np.amin([mindt,np.abs(list_physical_units[i].xfsPerPix)])
            
    #Obtain the number of electrons in each shot
    num_electrons=np.zeros(num_profiles, dtype=np.float64);
    for i in range(num_profiles): 
        num_electrons[i]=list_shot_to_shot[i].dumpecharge/Constants.E_CHARGE
            
    #To be safe with the master time, we set it to have a step half the minumum step
    dt=mindt/2

    #And create the master time vector in fs
    t=np.arange(mint,maxt+dt,dt)
    
    #Create the the arrays for the outputs, first index is always bunch number, and second index is group number
    averageECurrent=np.zeros((num_bunches, num_groups, len(t)), dtype=np.float64);       #Electron current in (#electrons/s)
    averageECOMslice=np.zeros((num_bunches, num_groups, len(t)), dtype=np.float64);      #Energy center of masses for each time in MeV
    averageERMSslice=np.zeros((num_bunches, num_groups, len(t)), dtype=np.float64);      #Energy dispersion for each time in MeV
    averageDistT=np.zeros((num_bunches, num_groups), dtype=np.float64);                 #Distance in time of the center of masses with respect to the center of the first bunch in fs
    averageDistE=np.zeros((num_bunches, num_groups), dtype=np.float64);                 #Distance in energy of the center of masses with respect to the center of the first bunch in MeV
    averageTRMS=np.zeros((num_bunches, num_groups), dtype=np.float64);                  #Total dispersion in time in fs
    averageERMS=np.zeros((num_bunches, num_groups), dtype=np.float64);                  #Total dispersion in energy in MeV
    eventTime=np.zeros((num_bunches, num_groups), dtype=np.uint64)
    eventFid=np.zeros((num_bunches, num_groups), dtype=np.uint32)
    
    #We treat each bunch separately, even group them separately
    for j in range(num_bunches):
        #Decide which profiles are going to be in which groups and average them together
        #Calculate interpolated profiles in time for comparison
        profilesT=np.zeros((num_profiles,len(t)), dtype=np.float64);
        for i in range(num_profiles): 
            distT=(list_image_stats[i][j].xCOM-list_image_stats[i][0].xCOM)*list_physical_units[i].xfsPerPix
            profilesT[i,:]=scipy.interpolate.interp1d(list_physical_units[i].xfs-distT,list_image_stats[i][j].xProfile, kind='linear',fill_value=0,bounds_error=False,assume_sorted=True)(t)
            
        #Decide of the groups based on correlation 
        group = np.zeros(num_profiles, dtype=np.int32)       #array that will indicate which group each profile sill correspond to
        group[:]=-1                             #initiated to -1
        
        for g in range(num_groups):                     #For each group
            currRef=np.where(group==-1)[0]  
            currRef=currRef[0]                  #We pick the first member to be the first one that has not been assigned to a group yet

            group[currRef]=g                   #We assign it the current group
            
            # We calculate the correlation of the first profile to the rest of available profiles
            err = np.zeros(num_profiles, dtype=np.float64);              
            for i in range(currRef, num_profiles): 
                if group[i] == -1:
                    err[i] = np.corrcoef(profilesT[currRef,:],profilesT[i,:])[0,1]**2;
                    
            #The 'shots_per_group-1' profiles with the highest correlation will be also assigned to the same group
            order=np.argsort(err)            
            for i in range(0,shots_per_group-1): 
                group[order[-(1+i)]]=g
                    
        #Once the groups have been decided, the averaging is performed
        for g in range(num_groups):                 #For each group
            for i in range(num_profiles):    
                if group[i]==g:             #We find the profiles that belong to that group and average them together
                
                    eventTime[j][g] = list_shot_to_shot[i].unixtime
                    eventFid[j][g] = list_shot_to_shot[i].fiducial
                    distT=(list_image_stats[i][j].xCOM-list_image_stats[i][0].xCOM)*list_physical_units[i].xfsPerPix #Distance in time converted form pixels to fs
                    distE=(list_image_stats[i][j].yCOM-list_image_stats[i][0].yCOM)*list_physical_units[i].yMeVPerPix #Distance in time converted form pixels to MeV
                    averageDistT[j,g]=averageDistT[j,g]+distT       #Accumulate it in the right group
                    averageDistE[j,g]=averageDistE[j,g]+distE       #Accumulate it in the right group
                    
                    averageTRMS[j,g]=averageTRMS[j,g]+list_image_stats[i][j].xRMS*list_physical_units[i].xfsPerPix   #Conversion to fs and accumulate it in the right group
                    averageERMS[j,g]=averageTRMS[j,g]+list_image_stats[i][j].yRMS*list_physical_units[i].yMeVPerPix  #Conversion to MeV and accumulate it in the right group
                                          
                    dt_old=list_physical_units[i].xfs[1]-list_physical_units[i].xfs[0]; # dt before interpolation   
                    eCurrent=list_image_stats[i][j].xProfile/(dt_old*1e-15)*num_electrons[i]                              #Electron current in electrons/s   
                    
                    eCOMslice=(list_image_stats[i][j].yCOMslice-list_image_stats[i][j].yCOM)*list_physical_units[i].yMeVPerPix #Center of mass in energy for each t converted to the right units
                    eRMSslice=list_image_stats[i][j].yRMSslice*list_physical_units[i].yMeVPerPix                                 #Energy dispersion for each t converted to the right units
                        
                    interp=scipy.interpolate.interp1d(list_physical_units[i].xfs-distT,eCurrent,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True)  #Interpolation to master time                    
                    averageECurrent[j,g,:]=averageECurrent[j,g,:]+interp(t);  #Accumulate it in the right group                    
                                                
                    interp=scipy.interpolate.interp1d(list_physical_units[i].xfs-distT,eCOMslice,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True) #Interpolation to master time
                    averageECOMslice[j,g,:]=averageECOMslice[j,g,:]+interp(t);          #Accumulate it in the right group
                    
                    interp=scipy.interpolate.interp1d(list_physical_units[i].xfs-distT,eRMSslice,kind='linear',fill_value=0,bounds_error=False,assume_sorted=True) #Interpolation to master time
                    averageERMSslice[j,g,:]=averageERMSslice[j,g,:]+interp(t);          #Accumulate it in the right group
                                  

            #Normalization off all the averaged stuff                      
            averageECurrent[j,g,:]=averageECurrent[j,g,:]/shots_per_group
            averageECOMslice[j,g,:]=averageECOMslice[j,g,:]/shots_per_group    
            averageERMSslice[j,g,:]=averageERMSslice[j,g,:]/shots_per_group
            averageDistT[j,g]=averageDistT[j,g]/shots_per_group
            averageDistE[j,g]=averageDistE[j,g]/shots_per_group
            averageTRMS[j,g]=averageTRMS[j,g]/shots_per_group
            averageERMS[j,g]=averageERMS[j,g]/shots_per_group     
            
    return AveragedProfiles(t, averageECurrent, averageECOMslice, 
        averageERMSslice, averageDistT, averageDistE, averageTRMS, 
        averageERMS, num_bunches, num_groups, eventTime, eventFid)

# http://stackoverflow.com/questions/26248654/numpy-return-0-with-divide-by-zero
def divideNoWarn(numer,denom,default):
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio=numer/denom
        ratio[ ~ np.isfinite(ratio)]=default  # NaN/+inf/-inf 
    return ratio

