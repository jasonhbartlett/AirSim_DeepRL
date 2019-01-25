import subprocess
import csv

from sys import platform, argv
from os import path
from time import sleep
from enum import Enum
from typing import Union

import numpy as np
import airsim

from as_settings import AS_Settings

class Environments(Enum):
    Blocks       = 0
    Maze         = 1
    Neighborhood = 2

# CONSTANTS

class DroneActIdx(Enum):
    VX       = 0
    VY       = 1
    VZ       = 2
    Yaw     = 3
#    Pitch    = 0
#    Yaw      = 1
#    Roll     = 2
#    Throttle = 3


class DroneAct(Enum):
    VxFW     = 0
    VxBW     = 1
    VyFW     = 2
    VyBW     = 3
    VzFW     = 4
    VzBW     = 5
    YawR    = 6
    YawL    = 7
#    PitchFW = 0
#    PitchBW = 1
#    RollLF  = 2
#    RollRG  = 3
#    YawLF   = 4
#    YawRG   = 5
#    ThroUP  = 6
#    ThroDW  = 7

class CarActIdx(Enum):
    VX       = 0
    VY       = 1
    VZ       = 2

class CarAct(Enum):
    VxFW     = 0
    VxBW     = 1
    VyFW     = 2
    VyBW     = 3
    VzFW     = 4
    VzBW     = 5


X = 0
Y = 1
Z = 2


class AS_Environment:

    def __init__(self, target_positions,  env:Environments=Environments.Maze , env_path:str='env', drone:bool=True,
                 settings_path:str=None,
                 stepped_simulation:bool=True, step_duration:float=0.1,
                 manual_mode:bool=False, joystick:Union[int,None]=0,
                 rendering:bool=True, lowres:bool=True,
                 crash_terminate=True, max_steps = 1000, min_reward=-1000, 
                 fast_deceleration = True):

        self.settings = AS_Settings(settings_path)

        environments = {
            Environments.Blocks      : {'subfolder': ''        , 'bin': ''},
            Environments.Maze        : {'subfolder': 'Car_Maze', 'bin': 'Car_Maze.exe'},
            Environments.Neighborhood: {'subfolder': 'AirSimNH', 'bin': 'AirSimNH.exe'},
        }

        #self.env = environments[env]

        self.env = ''
        for subpath in env_path.split(path.sep):
            self.env = path.join(self.env, subpath)
        for subpath in environments[env]['subfolder'].split(path.sep):
            self.env = path.join(self.env, subpath)
        self.env = path.join(self.env, environments[env]['bin'])

        # Process Object
        self.process = None
        self.process_args = {}

        self.drone = drone

        self.step_duration = step_duration

        self.manual_mode = not manual_mode
        self.stepped_simulation = stepped_simulation

        # AirSim API Client
        self.timeout = 15

        self.max_action_value = 250
        self.fast_deceleration = fast_deceleration

        if not self.drone:
            self.client = airsim.CarClient(timeout_value=self.timeout)
            self.settings.set('SimMode', 'Car')
            self.settings.clear('Vehicles', True)

            self.vehicle_name = 'PhysXCar'
            vehicle_type = 'PhysXCar'

            self.prev_act = [0, 0, 0]

            # Action conversion settings
            v_factor = 5

            self.possible_actions = {
                CarAct.VxFW: {'index': CarActIdx.VX, 'sign':  1, 'factor': v_factor, 'str': 'Vx Fwd'},
                CarAct.VxBW: {'index': CarActIdx.VX, 'sign': -1, 'factor': v_factor, 'str': 'Vx Bwd'},
                CarAct.VyFW: {'index': CarActIdx.VY, 'sign':  1, 'factor': v_factor, 'str': 'Vy Fwd'},
                CarAct.VyBW: {'index': CarActIdx.VY, 'sign': -1, 'factor': v_factor, 'str': 'Vy Bwd'},
                CarAct.VzFW: {'index': CarActIdx.VZ, 'sign':  1, 'factor': v_factor, 'str': 'Vz Fwd'},
                CarAct.VzBW: {'index': CarActIdx.VZ, 'sign': -1, 'factor': v_factor, 'str': 'Vz Bwd'},
            }

        else:
            self.client = airsim.MultirotorClient(timeout_value=self.timeout)
            self.settings.set('SimMode', 'Multirotor')
            self.settings.clear('Vehicles', True)

            self.vehicle_name = 'SimpleFlight'
            vehicle_type = 'SimpleFlight'

            self.prev_act = [0, 0, 0, 0]
            
            # action constants
            v_factor = 0.5
            yaw_factor = 5.0
            
            self.possible_actions = {
                DroneAct.VxFW: {'index': DroneActIdx.VX, 'sign':  1, 'factor': v_factor, 'str': 'Vx Fwd'},
                DroneAct.VxBW: {'index': DroneActIdx.VX, 'sign': -1, 'factor': v_factor, 'str': 'Vx Bwd'},
                DroneAct.VyFW: {'index': DroneActIdx.VY, 'sign':  1, 'factor': v_factor, 'str': 'Vy Fwd'},
                DroneAct.VyBW: {'index': DroneActIdx.VY, 'sign': -1, 'factor': v_factor, 'str': 'Vy Bwd'},
                DroneAct.VzFW: {'index': DroneActIdx.VZ, 'sign':  1, 'factor': v_factor, 'str': 'Vz Fwd'},
                DroneAct.VzBW: {'index': DroneActIdx.VZ, 'sign': -1, 'factor': v_factor, 'str': 'Vz Bwd'},
                DroneAct.YawR: {'index': DroneActIdx.Yaw, 'sign': 1, 'factor': yaw_factor, 'str': 'Yaw Right'},
                DroneAct.YawL: {'index': DroneActIdx.Yaw, 'sign': -1, 'factor': yaw_factor, 'str': 'Yaw Left'}, 
            }
            
#            # Action conversion settings
#            pitch_roll_factor = 5
#            yaw_factor = 10
#            throttle_factor = 15
#
#            self.possible_actions = {
#                    DroneAct.PitchFW: {'index': DroneActIdx.Pitch   , 'sign':  1, 'factor': pitch_roll_factor, 'str': 'Pitch Fwd'},
#                    DroneAct.PitchBW: {'index': DroneActIdx.Pitch   , 'sign': -1, 'factor': pitch_roll_factor, 'str': 'Pitch Bwd'},
#                    DroneAct.RollRG : {'index': DroneActIdx.Roll    , 'sign':  1, 'factor': pitch_roll_factor, 'str': 'Roll Rght'},
#                    DroneAct.RollLF : {'index': DroneActIdx.Roll    , 'sign': -1, 'factor': pitch_roll_factor, 'str': 'Roll Left'},
#                    DroneAct.YawRG  : {'index': DroneActIdx.Yaw     , 'sign':  1, 'factor': yaw_factor       , 'str': 'Yaw Right'},
#                    DroneAct.YawLF  : {'index': DroneActIdx.Yaw     , 'sign': -1, 'factor': yaw_factor       , 'str': 'Yaw  Left'},
#                    DroneAct.ThroUP : {'index': DroneActIdx.Throttle, 'sign':  1, 'factor': throttle_factor  , 'str': 'Thrt   Up'},
#                    DroneAct.ThroDW : {'index': DroneActIdx.Throttle, 'sign': -1, 'factor': throttle_factor  , 'str': 'Thrt  Dwn'},
#            }

        vehicle_settings_path = 'Vehicles/' + self.vehicle_name + '/'
        self.settings.set(vehicle_settings_path + 'VehicleType', vehicle_type)
        self.settings.set(vehicle_settings_path + 'DefaultVehicleState', 'Armed')
        self.settings.set(vehicle_settings_path + 'AutoCreate', True)
        self.settings.set(vehicle_settings_path + 'EnableCollisionPassthrogh', False)
        self.settings.set(vehicle_settings_path + 'EnableCollision', True)
        self.settings.set(vehicle_settings_path + 'AllowAPIAlways', self.manual_mode)

        if not rendering:
            self.settings.set('ViewMode', 'NoDisplay')
            self.settings.set('SubWindows', [])
        else:
            self.settings.set('ViewMode', 'SpringArmChase')



        self.process_args['windowed'] = ''


        if lowres:
            self.process_args['ResX'] = 640
            self.process_args['ResY'] = 480

        if joystick is not None:
            self.settings.set(vehicle_settings_path + 'RC/RemoteControlID', joystick)
            self.settings.set(vehicle_settings_path + 'RC/AllowAPIWhenDisconnected', self.manual_mode)

        # Reward Terminal Conditions
        self.crash_terminate = crash_terminate
        self.target_positions = target_positions

        self.max_steps = max_steps
        self.steps = 0

        self.last_dist_to_target = 0

        self.acc_reward = 0
        self.min_reward = min_reward

        self.step_penalty = -10

        self.collission_threshold = 5



        self.settings.dump()


    def reset(self, hard_reset=False, starting_position=(0, 0, 0)):

        if hard_reset and self._env_running():
            self.close()

        env_found = False
        try:
            env_found = self.client.ping()
        except:
            pass

        if hard_reset or not(env_found or self._env_running()):
            self._start()
            sleep(5)
            if not self.drone:
                self.client = airsim.CarClient(timeout_value=self.timeout)
            else:
                self.client = airsim.MultirotorClient(timeout_value=self.timeout)
            self.client.confirmConnection()

        self.client.reset()
        self.client.enableApiControl(self.manual_mode)
        self.client.armDisarm(True)

        # Move to Initial Position
        tmp_pose = self.client.simGetVehiclePose()
        tmp_pose.position.x_val = starting_position[X]
        tmp_pose.position.y_val = starting_position[Y]
        tmp_pose.position.z_val = starting_position[Z]
        tmp_pose.orientation.x_val = starting_position[X]
        tmp_pose.orientation.y_val = starting_position[Y]
        tmp_pose.orientation.z_val = starting_position[Z]
        self.client.simSetVehiclePose(tmp_pose, True)

        if self.stepped_simulation:
            self.client.simPause(True)



        last_pos = starting_position
        dist_accum = 0
        max_points = 10000
        first_target = True
        for target in self.target_positions:
            tmp_dis = np.sqrt((last_pos[X] - target[X]) ** 2 +
                                 (last_pos[Y] - target[Y]) ** 2 +
                                 (last_pos[Z] - target[Z]) ** 2 )
            dist_accum += tmp_dis

            if first_target:
                self.last_dist_to_target = tmp_dis
                first_target = False

            last_pos = target
        self.points_per_meter = max_points / dist_accum
        self.min_reward = -3 * max_points



    def close(self):

        self.client.enableApiControl(False)

        if self._env_running():
            if platform == 'win32':
                pid = self.process.pid
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)])
            else:
                self.process.kill()


    def _env_running(self):
        if self.process is not None:
            if self.process.poll() is None:
                return True

        return False

    def _start(self):
        args = [self.env]

        for key, val in self.process_args.items():
            tmp_arg = '-' + key

            if val is not None and val != '':
                tmp_arg += '=' + str(val)

            args.append(tmp_arg)

        self.process = subprocess.Popen(args)

    def step(self, action_id):

        self.steps += 1

        action = self.id2action(action_id)

        if self.stepped_simulation:
            self.client.simPause(False)

        if self.drone:
            # transform velocity according to the drone's orientation.... there is probably a way to do this more elegantly
            yaw = airsim.to_eularian_angles(self.client.simGetVehiclePose().orientation)[2]
            
            v_x = (action[DroneActIdx.VX.value]*np.cos(yaw) - action[DroneActIdx.VY.value]*np.sin(yaw))
            v_y = (action[DroneActIdx.VX.value]*np.sin(yaw) + action[DroneActIdx.VY.value]*np.cos(yaw))
            
            self.client.moveByVelocityAsync(v_x, v_y, action[DroneActIdx.VZ.value],self.step_duration,  
                                        yaw_mode=airsim.YawMode(is_rate=True,  yaw_or_rate = action[DroneActIdx.Yaw.value])).join()
#            self.client.moveByAngleThrottleAsync(action[DroneActIdx.Pitch.value], action[DroneActIdx.Roll.value],
#                                                 action[DroneActIdx.Throttle.value], action[DroneActIdx.Yaw.value],
#                                                 self.step_duration).join()
            

        else:
            self.client.moveByVelocity(action[CarActIdx.VX.value], action[CarActIdx.VY.value], action[CarActIdx.VZ.value],
                                       self.step_duration).join()

        if self.stepped_simulation:
            self.client.simContinueForTime(self.step_duration)

        state = self._get_state()
        step_reward = self._reward_function(state)
        terminal = self._terminal_state(state)

        self.acc_reward += step_reward

        return state, step_reward, terminal


    def _get_state(self):
        camera_view = self.client.simGetImages([airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)])
        camera_view = camera_view[0]
        pose = self.client.simGetVehiclePose()

        collision_info = self.client.simGetCollisionInfo()

        state = {'scene': camera_view,
                 'pose' : pose,
                 'coll' : collision_info}

        return state


    def _reward_function(self, state, check_collision=True):
        reward = 0

        current_target = self.target_positions[0]
        current_position = state['pose'].position
        current_position = (current_position.x_val, current_position.y_val, current_position.z_val)

        distance = np.sqrt((current_target[X] - current_position[X]) ** 2 +
                           (current_target[Y] - current_position[Y]) ** 2 +
                           (current_target[Z] - current_position[Z]) ** 2)

        advanced_distance = self.last_dist_to_target - distance
        reward += advanced_distance * self.points_per_meter

        self.last_dist_to_target = distance

        threshold = 0.1
        if distance < threshold:
            self.target_positions = self.target_positions[1:]
        
        if check_collision:
            collission = state['coll']
            if collission.has_collided:
                if collission.penetration_depth > self.collission_threshold:
                    reward -= 200 * collission.penetration_depth

        reward += self.step_penalty

        return reward

    def _terminal_state(self, state):

        collission = state['coll']
        if collission.has_collided:
            if collission.penetration_depth > self.collission_threshold:
                return True

        if self.steps > self.max_steps:
            return True

        if self.acc_reward < self.min_reward:
            return True

        return False

    def _parse_actid(self, action_id:int):
        if self.drone:
            return DroneAct(action_id)
        else:
            return CarAct(action_id)


    def actid2str(self, action_id):
        action_id = self._parse_actid(action_id)

        return self.possible_actions[action_id]['str']

    def id2action(self, action_id):

        action_id = self._parse_actid(action_id)

        action = self.prev_act #np.zeros(4)
        act = self.possible_actions[action_id]

        prev_val = self.prev_act[act['index'].value]
        sign = act['sign']
        factor = act['factor']
        tmp_act = prev_val + sign * factor
        # decelaration should be faster than acceleration, so the agent can brake efficiently
        if self.drone and self.fast_deceleration:
            if sign * prev_val < 0.0:
                tmp_act = prev_val + sign * factor * 3.0
                # stop the deceleration if it goes beyond 0 
                if sign * tmp_act > 0.0:
                    tmp_act = 0.0
        
        if tmp_act > self.max_action_value:
            action[act['index'].value] = self.max_action_value
        elif tmp_act < -self.max_action_value:
            action[act['index'].value] = -self.max_action_value
        else:
            action[act['index'].value] = tmp_act

        self.prev_act = action

        return action

    def read_recordings(self, rec_folders):
        '''
        parses the data from given AirSim recording folders into lists of states, action ids and rewards
        (not implemented for car)
        '''
        states = []
        action_ids = []
        rewards = []
        for folder in rec_folders:
            with open(path.join(folder,  'airsim_rec.txt')) as data_file:
                data_dicts = list(csv.DictReader(data_file,  delimiter='\t'))
                
                q = airsim.Quaternionr(w_val=float(data_dicts[0]["Q_W"]), x_val = float(data_dicts[0]["Q_X"]),
                                                        y_val= float(data_dicts[0]["Q_Y"]), z_val=float(data_dicts[0]["Q_Z"]))
                next_yaw = airsim.to_eularian_angles(q)[2]
                for i in range (0, len(data_dicts)-1):
                   # TODO store images instead of their paths 
                    states.append(path.join(folder,  data_dicts[i]["ImageFile"]))
                    # action choice
                    yaw = next_yaw
                    q = airsim.Quaternionr(w_val=float(data_dicts[i+1]["Q_W"]), x_val = float(data_dicts[i+1]["Q_X"]),
                                                            y_val= float(data_dicts[i+1]["Q_Y"]), z_val=float(data_dicts[i+1]["Q_Z"]))
                    next_yaw = airsim.to_eularian_angles(q)[2]
                    
                    
                    time_diff = float(data_dicts[i+1]["TimeStamp"]) - float(data_dicts[i]["TimeStamp"])
                    x_diff = float(data_dicts[i+1]["POS_X"]) - float(data_dicts[i]["POS_X"])
                    y_diff = float(data_dicts[i+1]["POS_Y"]) - float(data_dicts[i]["POS_Y"])
                    z_diff = float(data_dicts[i+1]["POS_Z"]) - float(data_dicts[i]["POS_Z"])
                    yaw_diff = next_yaw -yaw
                    
                    # transform the positional velocities to velocity with regard to the drones's axis
                    # TODO check signs, not entirely sure there
                    yaw_avg = yaw+ yaw_diff/2.0 #average angle
                    v_x = (x_diff*np.cos(yaw_avg) + y_diff*np.sin(yaw_avg))/time_diff
                    v_y = (-x_diff*np.sin(yaw_avg) + y_diff*np.cos(yaw_avg))/time_diff
                    v_z = z_diff/time_diff
                   
                    v_yaw = yaw_diff/time_diff
                    # angular velocity probably needs to be scaled for comparison (TODO find suitable factor)
                    v_yaw_scaling = 10.0 
                    
                    v_max_idx = np.argmax([abs(v) for v in [v_x,  v_y,  v_z,  v_yaw*v_yaw_scaling]])
                    if v_max_idx == 0:
                        if v_x >= 0: action = DroneAct.VxFW.value
                        else: action = DroneAct.VxBW.value
                    elif v_max_idx == 1:
                        if v_y >= 0: action = DroneAct.VyFW.value
                        else: action = DroneAct.VyBW.value
                    elif v_max_idx == 2:
                        if v_z >= 0: action = DroneAct.VzFW.value
                        else: action = DroneAct.VzBW.value
                    elif v_max_idx == 3:
                        if v_yaw >= 0: action = DroneAct.YawR.value
                        else: action = DroneAct.YawL.value
                    action_ids.append(action)
                    
                    # rewards
                    pos = airsim.Vector3r(x_val = float(data_dicts[i+1]["POS_X"]),
                                                        y_val = float(data_dicts[i+1]["POS_Y"]),
                                                        z_val = float(data_dicts[i+1]["POS_Z"]))

                    rewards.append(self._reward_function({"pose": airsim.Pose(position_val=pos,  orientation_val=q)},  check_collision=False))
        return states,  action_ids,  rewards


# Class Tests
if __name__ == '__main__':


    env_path = path.join('..', '..', '..', 'env')

    target_positions = [(0, 0, 0), (1, 1, -1)]

    env = AS_Environment(target_positions, env=Environments.Maze, env_path=env_path,
                         stepped_simulation=False, step_duration=1)
    env.reset()

    max_episodes = 3

    start_pos = [(0.5, 0.5, -2), (5, 5, -2), (3, 3, -2)]
    
    # fixed action sequence
    # a_seq = [5, 0, 0, 2, 2, 2, 3, 6, 6, 6, 6, 6, 6, 6, 7, 7 , 7,  7,  7]
    a_seq = [2, 2, 2, 2, 2, 2, 2]
    
    # Possible Actions
    a = [0, 1, 2, 3, 4, 5, 6, 7]
    # Action Probabilities
    p = [20, 9, 9, 9, 9, 9, 5, 5]
    p /= np.sum(p)

    for episode in range(max_episodes):
        env.reset(starting_position=start_pos[episode])

        terminal = False
        step = 1
        
        while not terminal:
            # follow the given action sequence, then do random stuff
            if step <= len(a_seq):
                action_id = a_seq[step-1]
            else:
                action_id = np.random.choice(a,p=p)
            action = env.actid2str(action_id)
            state, reward, terminal = env.step(action_id)
            print('Step: ', step, ' Distance: ', env.last_dist_to_target, ' Action: ', action_id, ' ',
                  action, ' Action Values: ', env.prev_act, ' Reward: ', reward, ' Total Reward: ', env.acc_reward )
            step +=1

    
    # read action sequence from recordings if given as args
    if len(argv) > 1:
        rec_folders = argv[1:]
        _,  actions,  _ = env.read_recordings(rec_folders)
        a_seq = actions
        
        print(a_seq)

    env.close()
