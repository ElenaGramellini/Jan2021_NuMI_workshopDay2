import math

# This matrix rotates NuMI coordinates to LArSoft (MicroBooNE) coordinates.
rotmatrix =	[	[0.92103853804025682,		0.0227135048039241207,		0.38880857519374290],
			[0.0000462540012621546684,	0.99829162468141475,		-0.0584279894529063024],
			[-0.38947144863934974,		0.0538324139386641073,		0.91946400794392302]       ]

# THIS is where you want to plug in NuMI coordinates to convert them to the BNB.
# They are currently set to the location of MicroBooNE in the NuMI coordinate system. 
NuMI_coordinates = [5502, 7259, 67270]

# Instead, you can declare a vector that you want to rotate from NuMI to BNB.
# NuMI_vector = [, , ]
# The vector pointing from the NuMI target to the MicroBooNE origin is [ 5487.1, 7232.57, 66553.408 ].

# These are the coordinates in the BNB coordinate system.  They are initialized with the correct offsets.
BNB_coordinates = [-31387.584221, -3316.402543, -60100.241397]

# If you want to rotate a vector from NuMI to BNB, then initialize it differently.
# BNB_vector = [0., 0., 0.]

# Multiply through the matrix and then normalize the vector.
for i in range(3):

    for j in range(3):

        BNB_coordinates[i] += rotmatrix[i][j] * NuMI_coordinates[j]
        # BNB_vector[i] += rotmatrix[i][j] * NuMI_vector[j]

print( "The NuMI coordinates = [%f, %f, %f]" %( NuMI_coordinates[0], NuMI_coordinates[1], NuMI_coordinates[2] ) )
print( "The BNB coordinates = [%f, %f, %f]" %( BNB_coordinates[0], BNB_coordinates[1], BNB_coordinates[2] ) )
#print( "The NuMI vector = [%f, %f, %f]" %( NuMI_vector[0], NuMI_vector[1], NuMI_vector[2] ) )
#print( "The BNB vector = [%f, %f, %f]" %( BNB_vector[0], BNB_vector[1], BNB_vector[2] ) )
