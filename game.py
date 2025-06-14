import pgzrun, pygame, pytmx
import pgzero.music as music
from pgzero.loaders import sounds
import os, time
#test
##############################################################
# CONSTANTS

WIDTH = 320
HEIGHT = 240
TITLE = "THESIS DUNGEON"
TILE_SIZE = 16
FRAME_RATE = 60
MOVEMENT_COOLDOWN = 0.15  # Time between moves in seconds (adjust for feel)

DEBUG_MODE_ON = False

LEVEL_SEQUENCE = [
    "level-1",
]


class AnimatedTile:
    """Lightweight animated tile class for Tiled animations"""

    def __init__(self, x, y, tile_gid, tmx_data):
        self.x = x
        self.y = y
        self.tile_gid = tile_gid
        self.tmx_data = tmx_data
        self.current_frame = 0
        self.last_frame_time = time.time()

        # Get animation data from Tiled
        self.frames = []
        self.frame_duration = 0.5  # Default duration

        # Extract animation frames from TMX data
        self._load_animation_data()

    def _load_animation_data(self):
        """Load animation frames from TMX tile data"""
        try:
            print(f"Loading animation data for tile GID: {self.tile_gid}")

            # Get tile properties directly - this is where PyTMX stores animation data
            tile_props = self.tmx_data.get_tile_properties_by_gid(self.tile_gid)
            print(f"Tile properties: {tile_props}")

            # Check if this tile has animation frames
            if tile_props and "frames" in tile_props:
                animation_frames = tile_props["frames"]
                print(f"Found {len(animation_frames)} animation frames")

                # Extract animation frames
                for i, frame in enumerate(animation_frames):
                    print(
                        f"Processing frame {i}: gid={frame.gid}, duration={frame.duration}"
                    )

                    # Get the surface for this frame using the GID directly
                    frame_surface = self.tmx_data.get_tile_image_by_gid(frame.gid)
                    if frame_surface:
                        self.frames.append(frame_surface)
                        # Use the duration from the frame (convert from ms to seconds)
                        self.frame_duration = frame.duration / 1000.0
                        print(f"Added frame {i}, duration: {self.frame_duration}s")
                    else:
                        print(
                            f"WARNING: Could not load frame surface for GID {frame.gid}"
                        )

                if self.frames:
                    print(f"Successfully loaded {len(self.frames)} animation frames")
                    return

            # If no animation found, use the static tile
            print("No animation frames found, using static tile")
            static_tile = self.tmx_data.get_tile_image_by_gid(self.tile_gid)
            if static_tile:
                self.frames = [static_tile]
                print("Added static tile as single frame")
            else:
                print("ERROR: Could not load static tile!")

        except Exception as e:
            print(f"Error loading animation for tile {self.tile_gid}: {e}")
            import traceback

            traceback.print_exc()
            # Fallback to static tile
            static_tile = self.tmx_data.get_tile_image_by_gid(self.tile_gid)
            if static_tile:
                self.frames = [static_tile]

    def update(self):
        """Update animation frame"""
        if len(self.frames) <= 1:
            return  # No animation needed

        current_time = time.time()
        if current_time - self.last_frame_time >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.last_frame_time = current_time

    def get_current_frame(self):
        """Get current animation frame"""
        if self.frames:
            return self.frames[self.current_frame]
        return None


class AnimatedSprite:
    def __init__(self, spritesheet_path, tile_size=16, animations=None):
        """
        Initialize animated sprite

        Args:
            spritesheet_path: Path to the spritesheet image
            tile_size: Size of each sprite frame (default 16x16)
            animations: Dict defining animations
        """
        self.tile_size = tile_size
        self.spritesheet = pygame.image.load(spritesheet_path)
        self.animations = animations or {}

        # Current animation state
        self.current_animation = None
        self.current_frame = 0
        self.last_frame_time = 0
        self.animation_finished = False

        # Cache for sprite frames to avoid repeated subsurface calls
        self.frame_cache = {}

        # Pre-load all frames into cache
        self._cache_frames()

    def _cache_frames(self):
        """Pre-load all animation frames into cache for better performance"""
        for anim_name, anim_data in self.animations.items():
            self.frame_cache[anim_name] = []
            for row, col in anim_data["frames"]:
                x = col * self.tile_size
                y = row * self.tile_size
                frame = self.spritesheet.subsurface(
                    x, y, self.tile_size, self.tile_size
                )
                self.frame_cache[anim_name].append(frame)

    def play_animation(self, animation_name, reset=True):
        """Start playing an animation"""
        if animation_name not in self.animations:
            print(f"Warning: Animation '{animation_name}' not found")
            return

        if self.current_animation != animation_name or reset:
            self.current_animation = animation_name
            self.current_frame = 0
            self.last_frame_time = time.time()
            self.animation_finished = False

    def update(self):
        """Update animation frame based on time"""
        if not self.current_animation or self.animation_finished:
            return

        current_time = time.time()
        anim_data = self.animations[self.current_animation]

        # Check if it's time to advance frame
        if current_time - self.last_frame_time >= anim_data["duration"]:
            self.current_frame += 1
            self.last_frame_time = current_time

            # Handle animation end
            if self.current_frame >= len(anim_data["frames"]):
                if anim_data.get("loop", True):
                    self.current_frame = 0  # Loop back to start
                else:
                    self.current_frame = len(anim_data["frames"]) - 1
                    self.animation_finished = True

    def get_current_frame(self):
        """Get the current frame surface"""
        if not self.current_animation:
            return None

        if self.current_animation in self.frame_cache:
            return self.frame_cache[self.current_animation][self.current_frame]

        return None

    def is_animation_finished(self):
        """Check if current animation is finished (for non-looping animations)"""
        return self.animation_finished


# Updated Player class with animation support
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.last_move_time = 0
        self.facing_direction = "right"  # Track facing direction
        self.is_moving = False
        self.movement_timer = 0  # Add movement timer for animation state

        # Attack state
        self.is_attacking = False
        self.attack_start_time = 0
        self.attack_duration = 0.5  # Total attack duration (5 frames * 100ms)

        # Hurt state
        self.is_hurt = False
        self.hurt_start_time = 0
        self.hurt_duration = 1.0  # 1 second of hurt state
        self.invincibility_duration = (
            1.5  # 1.5 seconds of invincibility after being hurt
        )
        self.is_invincible = False
        self.invincibility_start_time = 0

        # Health system
        self.max_health = 3
        self.current_health = 3

        # Snap position to grid on initialization
        self.x = (self.x // TILE_SIZE) * TILE_SIZE
        self.y = (self.y // TILE_SIZE) * TILE_SIZE

        # Define animations for the player
        player_animations = {
            "idle_right": {
                "frames": [(0, 0), (0, 1), (0, 2)],  # Row 0, columns 0-2
                "duration": 0.6,
                "loop": True,
            },
            "idle_left": {
                "frames": [(1, 0), (1, 1), (1, 2)],  # Row 1, columns 0-2
                "duration": 0.6,
                "loop": True,
            },
            "walk_right": {
                "frames": [(2, 0), (2, 1), (2, 2), (2, 3)],  # Row 2, columns 0-3
                "duration": 0.6,
                "loop": True,
            },
            "walk_left": {
                "frames": [(3, 0), (3, 1), (3, 2), (3, 3)],  # Row 3, columns 0-3
                "duration": 0.6,
                "loop": True,
            },
            "hurt_right": {
                "frames": [
                    (4, 1),
                    (4, 2),
                    (4, 3),
                    (4, 4),
                    (4, 5),
                ],  # Row 5, columns 1-5
                "duration": 0.6,  # 200ms per frame for hurt animation
                "loop": False,
            },
            "hurt_left": {
                "frames": [
                    (5, 1),
                    (5, 2),
                    (5, 3),
                    (5, 4),
                    (5, 5),
                ],  # Row 6, columns 1-5
                "duration": 0.6,  # 200ms per frame for hurt animation
                "loop": False,
            },
        }

        # Define sword animations (48x48 sprites)
        sword_animations = {
            "attack_left": {
                "frames": [
                    (0, 0),
                    (0, 1),
                    (0, 2),
                    (0, 3),
                    (0, 4),
                ],  # Row 0, columns 0-4
                "duration": 0.1,  # 100ms per frame
                "loop": False,
            },
            "attack_right": {
                "frames": [
                    (2, 0),
                    (2, 1),
                    (2, 2),
                    (2, 3),
                    (2, 4),
                ],  # Row 2, columns 0-4
                "duration": 0.1,  # 100ms per frame
                "loop": False,
            },
        }

        # Create animated sprites
        self.sprite = AnimatedSprite("images/player.png", TILE_SIZE, player_animations)
        self.sword_sprite = AnimatedSprite(
            "images/weapons_animated.png", 48, sword_animations
        )
        self.sprite.play_animation("idle_right")  # Start with idle animation

    def start_attack(self):
        """Start the attack animation if not already attacking or hurt"""
        if self.is_attacking or self.is_hurt:
            return False  # Already attacking or hurt

        self.is_attacking = True
        self.attack_start_time = time.time()
        sounds.sword_2.play()

        # Start appropriate sword animation based on facing direction
        if self.facing_direction == "right":
            self.sword_sprite.play_animation("attack_right", reset=True)
        else:
            self.sword_sprite.play_animation("attack_left", reset=True)

        return True

    def take_damage(self, damage=1):
        """Make the player take damage if not invincible"""
        if self.is_invincible or self.is_hurt:
            return False  # Already hurt or invincible

        self.current_health -= damage
        if self.current_health < 0:
            self.current_health = 0

        # Start hurt state
        self.is_hurt = True
        self.hurt_start_time = time.time()

        # Start invincibility
        self.is_invincible = True
        self.invincibility_start_time = time.time()

        # Cancel any current attack
        self.is_attacking = False

        # Start hurt animation based on facing direction
        if self.facing_direction == "right":
            self.sprite.play_animation("hurt_right", reset=True)
        else:
            self.sprite.play_animation("hurt_left", reset=True)

        print(
            f"Player took {damage} damage! Health: {self.current_health}/{self.max_health}"
        )
        return True

    def is_dead(self):
        """Check if player is dead"""
        return self.current_health <= 0

    def get_rect(self):
        """Get the player's collision rectangle"""
        return pygame.Rect(self.x, self.y, TILE_SIZE, TILE_SIZE)

    def update(self):
        """Update player animations and states"""
        current_time = time.time()

        # Update hurt state
        if self.is_hurt:
            # Check if hurt duration has elapsed
            if current_time - self.hurt_start_time >= self.hurt_duration:
                self.is_hurt = False
            else:
                # Update hurt animation
                self.sprite.update()
                return  # Don't process other states while hurt

        # Update invincibility state
        if self.is_invincible:
            if (
                current_time - self.invincibility_start_time
                >= self.invincibility_duration
            ):
                self.is_invincible = False

        # Update attack state
        if self.is_attacking:
            # Check if attack duration has elapsed
            if current_time - self.attack_start_time >= self.attack_duration:
                self.is_attacking = False
            else:
                # Update sword animation during attack
                self.sword_sprite.update()

        # Update movement timer
        if self.is_moving:
            self.movement_timer = (
                current_time + 0.3
            )  # Keep showing walk animation for 0.3 seconds

        # Determine if we should show walking or idle animation
        show_walking = current_time < self.movement_timer

        # Update animation state based on movement (only if not attacking or hurt)
        if not self.is_attacking and not self.is_hurt:
            if show_walking:
                if self.facing_direction == "right":
                    self.sprite.play_animation("walk_right", reset=False)
                else:
                    self.sprite.play_animation("walk_left", reset=False)
            else:
                if self.facing_direction == "right":
                    self.sprite.play_animation("idle_right", reset=False)
                else:
                    self.sprite.play_animation("idle_left", reset=False)

        # Update sprite animation
        self.sprite.update()

        # Reset movement flag (will be set again if moving)
        self.is_moving = False

    def get_sword_offset(self):
        """Calculate the offset for the sword sprite based on facing direction"""
        if self.facing_direction == "right":
            # Sword animation while facing right needs to be placed 16px to the left
            offset_x = -16
            offset_y = -16  # Center vertically (48-16)/2 = 16, so -16 to align
        else:
            # Sword animation while facing left needs to be placed 16px to the right
            offset_x = -16
            offset_y = -16  # Center vertically

        return offset_x, offset_y

    def draw(self, screen, camera_x, camera_y):
        """Draw the player and sword (if attacking) relative to camera position"""
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y

        # Apply flashing effect during invincibility
        should_draw = True
        if self.is_invincible and not self.is_hurt:
            # Flash every 0.1 seconds during invincibility
            flash_interval = 0.1
            time_since_invincible = time.time() - self.invincibility_start_time
            should_draw = int(time_since_invincible / flash_interval) % 2 == 0

        if should_draw:
            # Draw player sprite
            current_frame = self.sprite.get_current_frame()
            if current_frame:
                screen.blit(current_frame, (screen_x, screen_y))

        # Draw sword if attacking
        if self.is_attacking:
            sword_frame = self.sword_sprite.get_current_frame()
            if sword_frame:
                offset_x, offset_y = self.get_sword_offset()
                sword_x = screen_x + offset_x
                sword_y = screen_y + offset_y
                screen.blit(sword_frame, (sword_x, sword_y))

    def can_move(self, current_time):
        """Check if enough time has passed since last movement and not attacking or hurt"""
        if self.is_attacking or self.is_hurt:
            return False  # Can't move while attacking or hurt
        return current_time - self.last_move_time >= MOVEMENT_COOLDOWN

    def move(self, dx, dy, level_width, level_height, current_time):
        """Move the player one tile at a time with cooldown"""
        if not self.can_move(current_time):
            return False

        if dx != 0 and dy != 0:
            return False

        # Update facing direction
        if dx > 0:
            self.facing_direction = "right"
        elif dx < 0:
            self.facing_direction = "left"

        # Calculate new position
        new_x = self.x + (dx * TILE_SIZE)
        new_y = self.y + (dy * TILE_SIZE)

        # Boundary checking (simplified)
        moved = False
        if dx != 0:
            if new_x >= 0 and new_x <= level_width - TILE_SIZE:
                self.x = new_x
                moved = True
        elif dy != 0:
            if new_y >= 0 and new_y <= level_height - TILE_SIZE:
                self.y = new_y
                moved = True

        if moved:
            self.last_move_time = current_time
            self.is_moving = True  # Set movement flag for animation
            return True

        return False


class Enemy:
    def __init__(self, x, y, enemy_type="rat", enemy_movement="horizontal", blocks=2):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.enemy_movement = enemy_movement
        self.blocks = blocks

        # Snap position to grid on initialization
        self.x = (self.x // TILE_SIZE) * TILE_SIZE
        self.y = (self.y // TILE_SIZE) * TILE_SIZE

        # Store starting position for movement bounds
        self.start_x = self.x
        self.start_y = self.y

        # Movement state
        self.facing_direction = "right"  # Start facing right
        self.movement_state = "moving"  # 'moving' or 'idle'
        self.blocks_moved = 0  # How many blocks moved in current direction
        self.idle_start_time = 0
        self.idle_duration = 3.0  # 3 seconds idle time
        self.last_move_time = 0
        self.move_cooldown = 0.3  # Time between moves (adjust for speed)

        # Define animations for the enemy rat
        enemy_animations = {
            "idle_right": {
                "frames": [(0, 0), (0, 1)],  # Row 1, columns 1-2 (0-indexed)
                "duration": 0.6,
                "loop": True,
            },
            "idle_left": {
                "frames": [(1, 0), (1, 1)],  # Row 2, columns 1-2 (0-indexed)
                "duration": 0.6,
                "loop": True,
            },
            "walk_right": {
                "frames": [(2, 0), (2, 1), (2, 2)],  # Row 3, columns 1-3 (0-indexed)
                "duration": 0.4,
                "loop": True,
            },
            "walk_left": {
                "frames": [(3, 0), (3, 1), (3, 2)],  # Row 4, columns 1-3 (0-indexed)
                "duration": 0.4,
                "loop": True,
            },
        }

        # Create animated sprite
        self.sprite = AnimatedSprite(
            "images/enemy_rat.png", TILE_SIZE, enemy_animations
        )
        self.sprite.play_animation("walk_right")  # Start walking right

    def get_rect(self):
        """Get the enemy's collision rectangle"""
        return pygame.Rect(self.x, self.y, TILE_SIZE, TILE_SIZE)

    def update(self, level_loader=None):
        """Update enemy AI and animations"""
        current_time = time.time()

        if self.movement_state == "moving":
            # Check if it's time to move
            if current_time - self.last_move_time >= self.move_cooldown:
                # Determine movement direction based on enemy_movement type and facing direction
                dx, dy = 0, 0

                if self.enemy_movement == "horizontal":
                    dx = 1 if self.facing_direction == "right" else -1
                elif self.enemy_movement == "vertical":
                    dy = (
                        1 if self.facing_direction == "right" else -1
                    )  # 'right' = down, 'left' = up

                # Check if movement is valid (collision detection)
                new_x = self.x + (dx * TILE_SIZE)
                new_y = self.y + (dy * TILE_SIZE)

                can_move = True
                if level_loader:
                    can_move = not level_loader.is_position_blocked(new_x, new_y)

                if can_move:
                    # Move the enemy
                    self.x = new_x
                    self.y = new_y
                    self.blocks_moved += 1
                    self.last_move_time = current_time

                    # Check if we've moved the required number of blocks
                    if self.blocks_moved >= self.blocks:
                        # Switch to idle state
                        self.movement_state = "idle"
                        self.idle_start_time = current_time
                        self.blocks_moved = 0  # Reset block counter

                        # Update animation to idle
                        if self.enemy_movement == "horizontal":
                            if self.facing_direction == "right":
                                self.sprite.play_animation("idle_right")
                            else:
                                self.sprite.play_animation("idle_left")
                        elif self.enemy_movement == "vertical":
                            # For vertical movement, we use right/left animations based on direction
                            if self.facing_direction == "right":  # Moving down
                                self.sprite.play_animation("idle_right")
                            else:  # Moving up
                                self.sprite.play_animation("idle_left")
                else:
                    # Can't move (hit wall or obstacle), immediately switch to idle and turn around
                    self.movement_state = "idle"
                    self.idle_start_time = current_time
                    self.blocks_moved = 0

                    # Update animation to idle
                    if self.enemy_movement == "horizontal":
                        if self.facing_direction == "right":
                            self.sprite.play_animation("idle_right")
                        else:
                            self.sprite.play_animation("idle_left")
                    elif self.enemy_movement == "vertical":
                        if self.facing_direction == "right":
                            self.sprite.play_animation("idle_right")
                        else:
                            self.sprite.play_animation("idle_left")

            # Update walking animation
            else:
                if self.enemy_movement == "horizontal":
                    if self.facing_direction == "right":
                        self.sprite.play_animation("walk_right", reset=False)
                    else:
                        self.sprite.play_animation("walk_left", reset=False)
                elif self.enemy_movement == "vertical":
                    # For vertical movement, use right/left animations
                    if self.facing_direction == "right":  # Moving down
                        self.sprite.play_animation("walk_right", reset=False)
                    else:  # Moving up
                        self.sprite.play_animation("walk_left", reset=False)

        elif self.movement_state == "idle":
            # Check if idle time is over
            if current_time - self.idle_start_time >= self.idle_duration:
                # Switch direction and start moving again
                self.facing_direction = (
                    "left" if self.facing_direction == "right" else "right"
                )
                self.movement_state = "moving"
                self.last_move_time = current_time  # Reset move timer

                # Update animation to walking
                if self.enemy_movement == "horizontal":
                    if self.facing_direction == "right":
                        self.sprite.play_animation("walk_right")
                    else:
                        self.sprite.play_animation("walk_left")
                elif self.enemy_movement == "vertical":
                    if self.facing_direction == "right":  # Moving down
                        self.sprite.play_animation("walk_right")
                    else:  # Moving up
                        self.sprite.play_animation("walk_left")

        # Always update sprite animation
        self.sprite.update()

    def draw(self, screen, camera_x, camera_y):
        """Draw the enemy relative to camera position"""
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y

        # Draw enemy sprite
        current_frame = self.sprite.get_current_frame()
        if current_frame:
            screen.blit(current_frame, (screen_x, screen_y))


def toggle_debug_mode():
    """Toggle debug mode on/off"""
    global DEBUG_MODE_ON
    DEBUG_MODE_ON = not DEBUG_MODE_ON
    print(f"Debug mode: {'ON' if DEBUG_MODE_ON else 'OFF'}")


##############################################################
# UI


class UI:
    """Lightweight UI system for displaying hearts and other UI elements"""

    def __init__(self):
        # Load UI spritesheet
        self.ui_spritesheet = pygame.image.load("images/ui_hud.png")

        # Extract heart sprites (assuming 16x16 tiles)
        self.full_heart = self.ui_spritesheet.subsurface(0, 0, TILE_SIZE, TILE_SIZE)
        # If you have empty heart in column 2, row 1:
        # self.empty_heart = self.ui_spritesheet.subsurface(TILE_SIZE, 0, TILE_SIZE, TILE_SIZE)

        # Heart display settings
        self.heart_start_x = 16
        self.heart_start_y = 16
        self.heart_spacing = TILE_SIZE  # Hearts are placed side by side

    def draw(self, screen, player):
        """Draw the UI elements (hearts) on screen"""
        for i in range(player.max_health):
            heart_x = self.heart_start_x + (i * self.heart_spacing)
            heart_y = self.heart_start_y

            # Draw full hearts for current health, empty hearts for lost health
            if i < player.current_health:
                screen.blit(self.full_heart, (heart_x, heart_y))
            # If you have empty heart sprite, uncomment the following:
            # else:
            #     screen.blit(self.empty_heart, (heart_x, heart_y))


##############################################################
# LEVEL LOADER CLASS


class LevelLoader:
    def __init__(self, level_sequence):
        self.level_sequence = level_sequence
        self.current_level_index = 0
        self.tmx_data = None
        self.bg_surface = None
        self.camera_x = 0  # Camera stays at 0,0 for stationary view
        self.camera_y = 0
        self.entities = []  # List to hold all entities
        self.player = None  # Reference to the player object
        self.collision_grid = []  # 2D array for collision detection
        self.animated_tiles = []  # List of animated tiles
        self.ui = UI()  # Create UI system

        # Load the first level
        self.load_current_level()

    def check_player_enemy_collisions(self):
        """Check for collisions between player and enemies"""
        if not self.player or self.player.is_invincible:
            return

        player_rect = self.player.get_rect()

        for entity in self.entities:
            if isinstance(entity, Enemy):
                enemy_rect = entity.get_rect()
                if player_rect.colliderect(enemy_rect):
                    # Player collided with enemy
                    if self.player.take_damage(1):
                        print("Player hit by enemy!")
                        # Check if player is dead
                        if self.player.is_dead():
                            print("Game Over!")
                            # You can add game over logic here
                    break  # Only process one collision per frame

    def load_current_level(self):
        """Load the current level from the sequence"""
        if self.current_level_index >= len(self.level_sequence):
            return False

        level_name = self.level_sequence[self.current_level_index]
        tmx_path = os.path.join("data", "tmx", f"{level_name}.tmx")

        try:
            self.tmx_data = pytmx.load_pygame(tmx_path)
            self._create_collision_grid()  # Create collision grid first
            self._render_background()
            self._load_entities()
            self._load_animated_tiles()  # Load animated tiles
            return True
        except Exception as e:
            print(f"Error loading level {level_name}: {e}")
            return False

    def _create_collision_grid(self):
        """Create a 2D collision grid from the colliders layer"""
        if not self.tmx_data:
            return

        # Initialize collision grid with False (no collision)
        grid_width = self.tmx_data.width
        grid_height = self.tmx_data.height
        self.collision_grid = [
            [False for _ in range(grid_width)] for _ in range(grid_height)
        ]

        # Find the colliders layer
        colliders_layer = None
        for tmx_layer in self.tmx_data.layers:
            if tmx_layer.name == "colliders" and hasattr(tmx_layer, "data"):
                colliders_layer = tmx_layer
                break

        if not colliders_layer:
            print("Warning: 'colliders' layer not found in TMX file")
            return

        # Mark collision tiles as True
        for x, y, gid in colliders_layer:
            if gid:  # If there's a tile (gid > 0), it's a collision tile
                if 0 <= y < grid_height and 0 <= x < grid_width:
                    self.collision_grid[y][x] = True

        print(f"Created collision grid: {grid_width}x{grid_height}")

    def is_tile_blocked(self, tile_x, tile_y):
        """Check if a specific tile coordinate is blocked"""
        # Boundary check
        if (
            tile_x < 0
            or tile_y < 0
            or tile_y >= len(self.collision_grid)
            or tile_x >= len(self.collision_grid[0])
        ):
            return True  # Out of bounds = blocked

        return self.collision_grid[tile_y][tile_x]

    def is_position_blocked(self, pixel_x, pixel_y):
        """Check if a pixel position is blocked (converts to tile coordinates)"""
        tile_x = int(pixel_x // TILE_SIZE)
        tile_y = int(pixel_y // TILE_SIZE)
        return self.is_tile_blocked(tile_x, tile_y)

    def _render_background(self):
        """Pre-render the background and collision layers to a surface for better performance"""
        if not self.tmx_data:
            return

        # Create surface for the entire level
        level_width = self.tmx_data.width * self.tmx_data.tilewidth
        level_height = self.tmx_data.height * self.tmx_data.tileheight
        self.bg_surface = pygame.Surface((level_width, level_height))

        # Render layers in order: background layer first, then colliders layer on top
        # Note: We don't render animated layer here since it needs to be updated each frame
        layer_names = ["background", "colliders"]

        for layer_name in layer_names:
            layer = None
            for tmx_layer in self.tmx_data.layers:
                if tmx_layer.name == layer_name and hasattr(tmx_layer, "data"):
                    layer = tmx_layer
                    break

            if not layer:
                print(f"Warning: '{layer_name}' not found in TMX file")
                continue

            # Render all tiles from this layer
            for x, y, gid in layer:
                if gid:  # Only render if there's a tile (gid > 0)
                    tile = self.tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        self.bg_surface.blit(
                            tile,
                            (x * self.tmx_data.tilewidth, y * self.tmx_data.tileheight),
                        )

    def _load_entities(self):
        """Load entities from the object layer (updated to include enemies and music info)"""
        self.entities = []  # Clear existing entities
        self.player = None  # Reset player reference

        if not self.tmx_data:
            return

        # Find the entities object layer
        entities_layer = None
        for layer in self.tmx_data.layers:
            if layer.name == "entities":
                entities_layer = layer
                break

        if not entities_layer:
            print("Warning: 'entities' layer not found in TMX file")
            return

        # Create entity objects based on their names
        for obj in entities_layer:
            entity_name = obj.name.lower() if obj.name else ""

            if entity_name == "player":
                player = Player(obj.x, obj.y)
                self.entities.append(player)
                self.player = player  # Keep reference to player
                print(f"Created Player at ({obj.x}, {obj.y})")

            elif entity_name == "enemy":
                # Extract custom properties with defaults
                enemy_type = getattr(obj, "enemy_type", "rat")
                enemy_movement = getattr(obj, "enemy_movement", "horizontal")
                blocks = getattr(obj, "blocks", 2)

                # Try alternative property access methods if direct access fails
                if not hasattr(obj, "enemy_type") and hasattr(obj, "properties"):
                    enemy_type = obj.properties.get("enemy_type", "rat")
                    enemy_movement = obj.properties.get("enemy_movement", "horizontal")
                    blocks = obj.properties.get("blocks", 2)

                enemy = Enemy(obj.x, obj.y, enemy_type, enemy_movement, int(blocks))
                self.entities.append(enemy)
                print(
                    f"Created Enemy at ({obj.x}, {obj.y}) - Type: {enemy_type}, Movement: {enemy_movement}, Blocks: {blocks}"
                )

            elif entity_name == "info":
                # Handle info object for level settings like music
                music_file = None

                # Try to get music property using different methods
                if hasattr(obj, "music"):
                    music_file = obj.music
                elif hasattr(obj, "properties") and "music" in obj.properties:
                    music_file = obj.properties["music"]

                if music_file:
                    self._load_level_music(music_file)
                    print(f"Found music setting: {music_file}")
                else:
                    print("Info object found but no music property detected")

            else:
                print(f"Unknown entity type: {entity_name}")

    def _load_level_music(self, music_filename):
        """Load and play background music for the level"""
        try:
            # Stop any currently playing music
            music.stop()

            # Construct the full path to the music file
            music_path = os.path.join("music", f"{music_filename}.ogg")

            # Check if the file exists
            if os.path.exists(music_path):
                # Play the music on loop (-1 means infinite loop)
                music.play(music_filename)  # pgzero.music expects just the filename without extension and path
                print(f"Playing music: {music_path}")
            else:
                print(f"Warning: Music file not found: {music_path}")

        except Exception as e:
            print(f"Error loading music '{music_filename}': {e}")

    def _load_animated_tiles(self):
        """Load animated tiles from the animated layer"""
        self.animated_tiles = []

        if not self.tmx_data:
            return

        # Find the animated layer
        animated_layer = None
        for layer in self.tmx_data.layers:
            if layer.name == "animated" and hasattr(layer, "data"):
                animated_layer = layer
                break

        if not animated_layer:
            print("Warning: 'animated' layer not found in TMX file")
            return

        # Create animated tile objects
        for x, y, gid in animated_layer:
            if gid:  # Only process if there's a tile (gid > 0)
                pixel_x = x * self.tmx_data.tilewidth
                pixel_y = y * self.tmx_data.tileheight
                animated_tile = AnimatedTile(pixel_x, pixel_y, gid, self.tmx_data)
                self.animated_tiles.append(animated_tile)

        print(f"Loaded {len(self.animated_tiles)} animated tiles")

    def draw_debug_collision(self, screen):
        """Draw collision grid as red rectangles and animated tiles as blue rectangles (debug only)"""
        if not DEBUG_MODE_ON:
            return

        # Draw collision tiles in red
        if self.collision_grid:
            # Create a semi-transparent red surface for collision tiles
            for y in range(len(self.collision_grid)):
                for x in range(len(self.collision_grid[y])):
                    if self.collision_grid[y][x]:  # If this tile is a collision tile
                        # Calculate screen position (accounting for camera)
                        screen_x = (x * TILE_SIZE) - self.camera_x
                        screen_y = (y * TILE_SIZE) - self.camera_y

                        # Only draw if on screen (basic culling)
                        if (
                            -TILE_SIZE <= screen_x <= WIDTH
                            and -TILE_SIZE <= screen_y <= HEIGHT
                        ):
                            # Draw red rectangle with some transparency
                            red_surface = pygame.Surface((TILE_SIZE, TILE_SIZE))
                            red_surface.set_alpha(128)  # Semi-transparent
                            red_surface.fill((255, 0, 0))  # Red color
                            screen.blit(red_surface, (screen_x, screen_y))

        # Draw animated tiles in blue
        for tile in self.animated_tiles:
            # Calculate screen position (accounting for camera)
            screen_x = tile.x - self.camera_x
            screen_y = tile.y - self.camera_y

            # Only draw if on screen (basic culling for performance)
            if -TILE_SIZE <= screen_x <= WIDTH and -TILE_SIZE <= screen_y <= HEIGHT:
                # Draw blue rectangle with some transparency
                blue_surface = pygame.Surface((TILE_SIZE, TILE_SIZE))
                blue_surface.set_alpha(128)  # Semi-transparent
                blue_surface.fill((0, 0, 255))  # Blue color
                screen.blit(blue_surface, (screen_x, screen_y))

    def update(self):
        """Update animated tiles, entities, and check collisions"""
        # Update animated tiles
        for tile in self.animated_tiles:
            tile.update()

        # Update all entities
        for entity in self.entities:
            if hasattr(entity, 'update'):
                # Pass level_loader reference to enemies for collision detection
                if isinstance(entity, Enemy):
                    entity.update(level_loader=self)
                else:
                    entity.update()

        # Check for player-enemy collisions
        self.check_player_enemy_collisions()

    def draw(self, screen):
        """Draw the current level's background layer, animated tiles, and entities"""
        if self.bg_surface:
            # Draw the background from the stationary camera position (0,0)
            screen_rect = pygame.Rect(self.camera_x, self.camera_y, WIDTH, HEIGHT)
            screen.blit(self.bg_surface, (0, 0), screen_rect)

        # Draw animated tiles
        for tile in self.animated_tiles:
            current_frame = tile.get_current_frame()
            if current_frame:
                screen_x = tile.x - self.camera_x
                screen_y = tile.y - self.camera_y
                # Only draw if on screen (basic culling for performance)
                if (-TILE_SIZE <= screen_x <= WIDTH and -TILE_SIZE <= screen_y <= HEIGHT):
                    screen.blit(current_frame, (screen_x, screen_y))

        # Draw all entities
        for entity in self.entities:
            entity.draw(screen, self.camera_x, self.camera_y)

        # Draw UI with player reference
        if self.player:
            self.ui.draw(screen, self.player)

        self.draw_debug_collision(screen)

    def next_level(self):
        """Load the next level in the sequence"""
        self.current_level_index += 1
        return self.load_current_level()

    def get_level_size(self):
        """Get the size of the current level in pixels"""
        if self.tmx_data:
            return (
                self.tmx_data.width * self.tmx_data.tilewidth,
                self.tmx_data.height * self.tmx_data.tileheight,
            )
        return (0, 0)

    def move_player(self, dx, dy):
        """Move the player if it exists and the move is valid"""
        if self.player:
            level_width, level_height = self.get_level_size()

            # Calculate new position in pixels
            new_x = self.player.x + (dx * TILE_SIZE)
            new_y = self.player.y + (dy * TILE_SIZE)

            # Check collision at new position
            if not self.is_position_blocked(new_x, new_y):
                # Get current time in seconds
                current_time = pygame.time.get_ticks() / 1000.0
                return self.player.move(dx, dy, level_width, level_height, current_time)
            else:
                # Movement blocked by collision
                return False
        return False


##############################################################
# PYGAME ZERO IMPLEMENTATION

# Global level loader instance
level_loader = LevelLoader(LEVEL_SEQUENCE)


def draw():
    """Pygame Zero draw function"""
    screen.clear()
    level_loader.draw(screen.surface)


def update():
    """Pygame Zero update function - handle continuous key presses with tile-based movement"""
    # Update level (animated tiles and entities)
    level_loader.update()

    # Handle debug mode toggle
    if keyboard.d:
        toggle_debug_mode()
        # Small delay to prevent rapid toggling
        import time

        time.sleep(0.2)

    # Handle attack input (SPACE key)
    if keyboard.space:
        if level_loader.player:
            level_loader.player.start_attack()
        # Small delay to prevent rapid attack spamming
        import time

        time.sleep(0.1)

    # Handle continuous movement (tile-by-tile while key is held)
    # Only allow one direction at a time to prevent diagonal movement
    # Also prevent movement while attacking
    if not (level_loader.player and level_loader.player.is_attacking):
        if keyboard.left and not (keyboard.right or keyboard.up or keyboard.down):
            level_loader.move_player(-1, 0)
        elif keyboard.right and not (keyboard.left or keyboard.up or keyboard.down):
            level_loader.move_player(1, 0)
        elif keyboard.up and not (keyboard.left or keyboard.right or keyboard.down):
            level_loader.move_player(0, -1)
        elif keyboard.down and not (keyboard.left or keyboard.right or keyboard.up):
            level_loader.move_player(0, 1)


pgzrun.go()
