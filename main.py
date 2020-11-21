import pygame
import sys
import math
import numpy as np
import random
import time
from screeninfo import get_monitors


pygame.mixer.init()
pygame.init()

fps = 60
fpsClock = pygame.time.Clock()
sound_effects = True
high_score = 0

monitor = get_monitors()[0]
screen_shape = screen_width, screen_height = (monitor.width, monitor.height)
screen_center = (screen_width / 2, screen_height / 2)
screen = pygame.display.set_mode(screen_shape, pygame.FULLSCREEN)

game_font = pygame.font.Font('assets/Aller_Rg.ttf', 32)
game_font_small = pygame.font.Font('assets/Aller_Rg.ttf', 26)


def calculate_gravity(pos, black_hole_group):
    GRAVITATIONAL_CONSTANT = 180
    MAX_GRAVITY = 20
    vector = np.array([0., 0.])
    for black_hole in black_hole_group:
        relative_pos = tuple(a - b for a,b in zip(pos, black_hole.rect.center))
        angle = math.atan(relative_pos[1] / relative_pos[0]) if relative_pos[0] != 0 else math.pi / 2
        distance = math.sqrt(relative_pos[0]**2 + relative_pos[1]**2)
        vector += np.array([-GRAVITATIONAL_CONSTANT / math.copysign(distance**1.1, rel) if distance != 0 else 0 for rel in relative_pos])
    net_gravity = math.sqrt(vector[0]**2 + vector[1]**2)
    if net_gravity > MAX_GRAVITY:
        vector *= MAX_GRAVITY / net_gravity
    return vector


def score_display():
    score_surface = game_font.render(f'Score: {score}', True, (200, 200, 200))
    score_rect = score_surface.get_rect(center=(int(screen_shape[0] / 2), 30))
    screen.blit(score_surface, score_rect)

    lives_surface = game_font.render(f'Lives: {lives}', True, (170, 170, 170))
    lives_rect = lives_surface.get_rect(center=(int(screen_shape[0] / 2), 80))
    screen.blit(lives_surface, lives_rect)


class BlackHole(pygame.sprite.Sprite):
    raw_image = pygame.image.load('assets/black_hole.png').convert()

    def __init__(self, pos, size=None):
        super().__init__()
        self.image = self.raw_image.copy()
        self.size = size
        if size is not None:
            self.image = pygame.transform.scale(self.image, (size, size))
        self.rect = self.image.get_rect(center=pos)

    @property
    def gravity(self):
        return self.size / 100

    def enlarge(self):
        if self.size <= 200:
            self.size += 3
            self.image = pygame.transform.scale(self.raw_image.copy(), (self.size, self.size))


class Fighter(pygame.sprite.Sprite):
    directions = {'right': {'angle': 0},
                  'downright': {'angle': math.radians(45)},
                  'down': {'angle': math.radians(90)},
                  'downleft': {'angle': math.radians(135)},
                  'left': {'angle': math.radians(180)},
                  'upleft': {'angle': math.radians(225)},
                  'up': {'angle': math.radians(270)},
                  'upright': {'angle': math.radians(315)}}
    for direction in directions.keys():
        directions[direction]['image'] = pygame.image.load(f'assets/fighter_{direction}.png')
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')
    death_image = pygame.image.load('assets/fighter-death.png')
    death_sound = pygame.mixer.Sound('assets/fighter-death.wav')
    death_time = None

    def __init__(self, pos, screen_shape):
        super().__init__()
        self.screen_shape = screen_shape
        self.initial_pos = pos
        self.velocity = [0, 0]  # speed x, speed y
        self.direction = 'right'  # degrees
        self.acceleration = 1

        self.image = self.directions[self.direction]['image']
        self.rect = self.image.get_rect(center=pos)

    def _update_direction(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w] and keys[pygame.K_d]:
            self.direction = 'upright'
        elif keys[pygame.K_d] and keys[pygame.K_s]:
            self.direction = 'downright'
        elif keys[pygame.K_s] and keys[pygame.K_a]:
            self.direction = 'downleft'
        elif keys[pygame.K_a] and keys[pygame.K_w]:
            self.direction = 'upleft'
        elif keys[pygame.K_w]:
            self.direction = 'up'
        elif keys[pygame.K_d]:
            self.direction = 'right'
        elif keys[pygame.K_s]:
            self.direction = 'down'
        elif keys[pygame.K_a]:
            self.direction = 'left'
        
    def _move(self):
        new_center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        for i in range(2):
            if new_center[i] < 0:
                new_center[i] = 0
                if self.velocity[i] <= 0:
                    self.velocity[i] = 0
                self.velocity[i] = 0
            elif new_center[i] > self.screen_shape[i]:
                new_center[i] = self.screen_shape[i]
                if self.velocity[i] >= 0:
                    self.velocity[i] = 0
        self.rect.center = tuple(new_center)

    def _accelerate(self, gravity):
        DRAG = 0.05
        if self.death_time is None:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_a] or keys[pygame.K_s] or keys[pygame.K_d]:
                angle = self.directions[self.direction]['angle']
                self.velocity = [math.cos(angle) * self.acceleration + self.velocity[0],
                                math.sin(angle) * self.acceleration + self.velocity[1]]
        self.velocity = [a + b for a,b in zip(self.velocity, gravity)]
        self.velocity = [v * (1 - DRAG) for v in self.velocity]

    def update(self, gravity):
        if self.death_time:
            if time.time() > self.death_time + 1:
                self.reset()
        else:
            self._update_direction()
            self.image = self.directions[self.direction]['image']
        self._accelerate(gravity)
        self._move()

    def draw(self, screen):
        screen.blit(self.image, self.rect)

    def reset(self):
        self.direction = 'right'
        self.velocity = [0, 0]
        self.rect.center = self.initial_pos
        self.death_time = None
    
    def fire(self):
        if self.death_time is None:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            init_x, init_y = self.rect.center
            delta_x = mouse_x - init_x
            delta_y = init_y - mouse_y
            angle = math.degrees(math.atan(delta_y / delta_x)) if delta_x != 0 else 0
            if delta_x < 0:
                angle += 180
            torpedo_group.add(Torpedo((init_x, init_y), angle, screen_shape, black_hole_group))
            if sound_effects:
                self.torpedo_sound.play()

    def destroy(self, angle):
        if self.death_time is None:
            self.image = pygame.transform.rotate(self.death_image.copy(), angle)
            if sound_effects:
                self.death_sound.play()
            self.death_time = time.time()


class Crosshair(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.image.load('assets/crosshair.png')
        self.rect = self.image.get_rect()

    def update(self):
        self.rect.center = pygame.mouse.get_pos()

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Torpedo(pygame.sprite.Sprite):
    raw_image = pygame.image.load('assets/torpedo.png').convert_alpha()

    def __init__(self, pos, angle, screen_shape, black_hole_group, speed=20):
        super().__init__()
        self.image = self.raw_image.copy()
        self.speed = speed
        self.angle = angle
        velocity_x = math.cos(math.radians(angle)) * self.speed
        velocity_y = -math.sin(math.radians(angle)) * self.speed
        self.velocity = np.array([velocity_x, velocity_y])
        self.image = pygame.transform.rotate(self.image, self.angle)
        self.rect = self.image.get_rect(center=pos)
        self.screen_shape =  screen_shape
        self.black_hole_group = black_hole_group

    def _calculate_gravity(self):
        return calculate_gravity(self.rect.center, self.black_hole_group)

    def update(self):
        init_angle = self.angle
        gravity = self._calculate_gravity()
        self.velocity = [a + b for a,b in zip(self.velocity, gravity)]
        self.rect.center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        self.angle = math.degrees(math.atan(-self.velocity[1] / self.velocity[0])) if self.velocity[0] != 0 else 90
        if self.velocity[0] < 0:
            self.angle += 180
        # self.image = pygame.transform.rotate(self.image, self.angle - init_angle)
        self.image = pygame.transform.rotate(self.raw_image.copy(), self.angle)
        if not 0 < self.rect.center[0] < self.screen_shape[0] or not 0 < self.rect.center[1] < self.screen_shape[1]:
            self.kill()
        elif pygame.sprite.spritecollide(self, self.black_hole_group, False):
            self.kill()
    
    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Drone(pygame.sprite.Sprite):
    image = pygame.image.load('assets/drone.png').convert_alpha()
    image_death = pygame.image.load('assets/drone-death.png').convert_alpha()
    sound_death = pygame.mixer.Sound('assets/drone-death.wav')
    death_time = None
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')

    def __init__(self, screen_shape, black_hole_group):
        super().__init__()
        self.screen_shape = screen_shape
        self.black_hole_group = black_hole_group
        speed = 8
        if random.choice([True, False]):
            pos = (random.choice([0, screen_shape[0]]), random.randrange(0, screen_shape[1]))
            self.velocity = (speed * (1 if pos[0] == 0 else -1), random.choice([-3, 3]))
        else:
            pos = (random.randrange(0, screen_shape[0]), random.choice([0, screen_shape[1]]))
            self.velocity = (random.choice([-3, 3]), speed * (1 if pos[1] == 0 else -1))
        self.rect = self.image.get_rect(center=pos)
        self.drag = 0.1
        self.init_time = time.time()
        self.last_fired_time = self.init_time

    def _calculate_gravity(self):
        return calculate_gravity(self.rect.center, self.black_hole_group)

    def update(self):
        gravity = self._calculate_gravity()
        self.velocity = [(a + b) * (1 - self.drag) for a,b in zip(self.velocity, gravity)]
        self.rect.center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        if not 0 <= self.rect.center[0] <= self.screen_shape[0] or not 0 <= self.rect.center[1] <= self.screen_shape[1]:
            self.kill()
        elif pygame.sprite.spritecollide(self, self.black_hole_group, False):
            self.kill()
        elif time.time() > self.init_time + 10:
            self.kill()
        elif time.time() > self.last_fired_time + 1.5 and self.death_time is None:
            for angle in np.arange(0, 7) * 45:
                enemy_torpedo_group.add(Torpedo(self.rect.center, angle, self.screen_shape, self.black_hole_group, speed=10))
            if sound_effects:
                self.torpedo_sound.play()
            self.last_fired_time = time.time()
        elif self.death_time:
            if time.time() > self.death_time + 0.5:
                self.kill()

    def draw(self, screen):
        screen.blit(self.image, self.rect)

    def destroy(self, angle):
        if self.death_time is None:
            self.image = pygame.transform.rotate(self.image_death.copy(), angle)
            if sound_effects:
                self.sound_death.play()
            self.death_time = time.time()


def setup_game():
    global score, lives, dronespawn_freq
    score = 0
    lives = 5
    dronespawn_freq = 3000
    black_hole_group.empty()
    for _ in range(2):
        pos = (random.randrange(200, screen_shape[0] - 200), random.randrange(200, screen_shape[1] - 200))
        size = random.randrange(50, 200)
        black_hole = BlackHole(pos, size=size)
        black_hole_group.add(black_hole)
    pygame.time.set_timer(DRONESPAWN, dronespawn_freq)
    pygame.time.set_timer(INCREASEDRONESPAWN, 3000)
    fighter.reset()

game_over_sound = pygame.mixer.Sound('assets/game-over.wav')
game_over_10plus = pygame.mixer.Sound('assets/game-over-10plus.wav')
game_over_20plus = pygame.mixer.Sound('assets/game-over-20plus.wav')
game_over_50plus = pygame.mixer.Sound('assets/game-over-50plus.wav')
def game_over():
    global high_score, score
    high_score = max([score, high_score])

    fighter.reset()
    drone_group.empty()
    torpedo_group.empty()
    enemy_torpedo_group.empty()
    pygame.time.set_timer(DRONESPAWN, 0)


START_SCREEN_OFFSET = np.array([screen_width - 350, screen_height - 480]) / 2
def is_mouse_over_button(button):
    button_coords = {'play': ((98, 281), (230, 341)),
                     'quit': ((12, 380), (91, 402)),
                     'music': ((148, 385), (159, 396)),
                     'effects': ((256, 385), (266, 396))}
    area = button_coords.get(button)
    area = tuple(np.array(point) + START_SCREEN_OFFSET for point in area)
    pos = pygame.mouse.get_pos()
    return area[0][0] < pos[0] < area[1][0] and area[0][1] < pos[1] < area[1][1]


black_hole_group = pygame.sprite.Group()
fighter = Fighter((100, 100), screen_shape)
torpedo_group = pygame.sprite.Group()
enemy_torpedo_group = pygame.sprite.Group()

pygame.mouse.set_visible(False)
crosshair = Crosshair()

DRONESPAWN = pygame.USEREVENT
INCREASEDRONESPAWN = pygame.USEREVENT + 1
drone_group = pygame.sprite.Group()

start_screen = pygame.image.load('assets/start-screen.png').convert()


game_active = False
pygame.mixer.music.load('assets/game-music.wav')
pygame.mixer.music.set_volume(0.3)
pygame.mixer.music.play()
setup_game()


while True:
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
    # ======= GAME LOOP ========== #
    if game_active:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game_active = False
                    game_over()
                    break
                elif event.key == pygame.K_r:
                    fighter.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                fighter.fire()
            elif event.type == DRONESPAWN:
                drone_group.add(Drone(screen_shape, black_hole_group))
            elif event.type == INCREASEDRONESPAWN:
                dronespawn_freq = max([0, dronespawn_freq - 15])
                pygame.time.set_timer(DRONESPAWN, dronespawn_freq)
                for black_hole in black_hole_group:
                    black_hole.enlarge()
    
        fighter_collions = pygame.sprite.spritecollide(fighter, enemy_torpedo_group, True)
        if fighter_collions:
            lives -= 1
            if lives < 0:
                if sound_effects:
                    if score >= 50:
                        game_over_50plus.play()
                    elif score >= 20:
                        game_over_20plus.play()
                    elif score >= 10:
                        game_over_10plus.play()
                    else:
                        game_over_sound.play()
                game_active = False
                game_over()
            else:
                fighter.destroy(fighter_collions[0].angle)

        hit_drones = pygame.sprite.groupcollide(drone_group, torpedo_group, False, True)
        if hit_drones:
            for drone, torpedos in hit_drones.items():
                score = score + 1
                drone.destroy(torpedos[0].angle)

        # Update
        gravity = calculate_gravity(fighter.rect.center, black_hole_group)
        fighter.update(gravity)
        crosshair.update()
        torpedo_group.update()
        enemy_torpedo_group.update()
        drone_group.update()

        # Draw
        screen.fill((0, 0, 0))
        score_display()
        black_hole_group.draw(screen)
        fighter.draw(screen)
        crosshair.draw(screen)
        torpedo_group.draw(screen)
        enemy_torpedo_group.draw(screen)
        drone_group.draw(screen)
    # ======= END GAME LOOP ========== #

    # ======= MENU LOOP ========== #
    else:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if is_mouse_over_button('quit'):
                    pygame.quit()
                    sys.exit()
                elif is_mouse_over_button('play'):
                    game_active = True
                    setup_game()
                elif is_mouse_over_button('music'):
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                    else:
                        pygame.mixer.music.play()
                elif is_mouse_over_button('effects'):
                    sound_effects = not sound_effects

        # Update
        crosshair.update()

        # Draw
        screen.fill((0, 0, 0))
        screen.blit(start_screen, (785, 300))

        score_render = game_font_small.render(f'Score: {score}', True, (255, 255, 255))
        score_render_rect = score_render.get_rect(center=tuple(START_SCREEN_OFFSET + np.array([175, 170])))
        screen.blit(score_render, score_render_rect)
        
        high_score_render = game_font_small.render('High Score', True, (255, 255, 255))
        high_score_render_rect = high_score_render.get_rect(center=tuple(START_SCREEN_OFFSET + np.array([175, 220])))
        screen.blit(high_score_render, high_score_render_rect)

        high_score_value_render = game_font_small.render(str(high_score), True, (255, 255, 255))
        high_score_value_render_rect = high_score_value_render.get_rect(center=tuple(START_SCREEN_OFFSET + np.array([175, 250])))
        screen.blit(high_score_value_render, high_score_value_render_rect)

        crosshair.draw(screen)
    # ======= END MENU LOOP ========== #

    pygame.display.flip()
    fpsClock.tick(fps)
